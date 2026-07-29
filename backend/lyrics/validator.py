"""Deterministic lyrics normalization, parsing, and safety checks."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser

from backend.lyrics.constants import (
    MAX_LINE_LENGTH,
    MAX_RAW_LYRICS_LENGTH,
    SUPPORTED_LANGUAGES,
    SUPPORTED_SECTION_TYPES,
)
from backend.lyrics.errors import LyricsValidationError
from backend.lyrics.interfaces import LyricsSection

_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SCRIPT_PATTERN = re.compile(
    r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL
)
_HEADER_PATTERN = re.compile(r"^\[([^\]]+)]$")
_NUMBER_SUFFIX_PATTERN = re.compile(r"\s+\d+$")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


@dataclass(frozen=True, slots=True)
class LyricsValidationResult:
    valid: bool
    normalized_lyrics: str
    sections: tuple[LyricsSection, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    character_count: int
    line_count: int
    section_count: int
    repetition_ratio: float


def normalize_plain_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _CONTROL_PATTERN.sub("", value)
    value = _SCRIPT_PATTERN.sub("", value)
    if "<" in value and ">" in value:
        parser = _TextExtractor()
        parser.feed(value)
        value = "".join(parser.parts)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(lines).strip()


def normalize_section_type(label: str) -> str:
    normalized = label.strip().lower().replace("-", " ").replace("_", " ")
    normalized = _NUMBER_SUFFIX_PATTERN.sub("", normalized)
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized


def validate_requested_structure(structure: tuple[str, ...]) -> None:
    unsupported = sorted(set(structure) - SUPPORTED_SECTION_TYPES)
    if unsupported:
        raise LyricsValidationError(
            f"지원하지 않는 가사 섹션입니다: {', '.join(unsupported)}"
        )


def validate_lyrics(raw_lyrics: str, language: str = "ko") -> LyricsValidationResult:
    if language not in SUPPORTED_LANGUAGES:
        raise LyricsValidationError("지원하지 않는 가사 언어입니다.")
    normalized = normalize_plain_text(raw_lyrics)
    if not normalized:
        raise LyricsValidationError("가사가 비어 있습니다.")
    if len(normalized) > MAX_RAW_LYRICS_LENGTH:
        raise LyricsValidationError("가사 길이 제한을 초과했습니다.")

    warnings: list[str] = []
    errors: list[str] = []
    sections: list[LyricsSection] = []
    current_type: str | None = None
    current_lines: list[str] = []
    saw_header = False

    def flush() -> None:
        nonlocal current_lines
        if current_type is not None and current_lines:
            sections.append(LyricsSection(current_type, tuple(current_lines)))
        current_lines = []

    for line in normalized.splitlines():
        if not line:
            continue
        match = _HEADER_PATTERN.match(line)
        if match:
            section_type = normalize_section_type(match.group(1))
            if section_type not in SUPPORTED_SECTION_TYPES:
                errors.append(f"지원하지 않는 섹션 태그입니다: {match.group(1)}")
                continue
            flush()
            current_type = section_type
            saw_header = True
            continue
        if len(line) > MAX_LINE_LENGTH:
            errors.append(f"한 줄 길이 제한({MAX_LINE_LENGTH}자)을 초과했습니다.")
        if current_type is None:
            current_type = "verse"
        current_lines.append(line)
    flush()

    if not sections:
        errors.append("가사 섹션 또는 가사 줄이 없습니다.")
    if not saw_header:
        warnings.append("섹션 태그가 없어 전체 가사를 Verse로 정리했습니다.")
    section_types = [section.section_type for section in sections]
    if "chorus" not in section_types and "final_chorus" not in section_types:
        warnings.append("후렴이 정의되지 않았습니다.")

    lyric_lines = [line for section in sections for line in section.lines]
    counts = Counter(line.casefold() for line in lyric_lines if line)
    max_repeats = max(counts.values(), default=0)
    repetition_ratio = max_repeats / len(lyric_lines) if lyric_lines else 0.0
    if max_repeats >= 3 and repetition_ratio >= 0.4:
        warnings.append("동일 문장이 과도하게 반복됩니다.")
    if "\n\n\n" in normalized:
        warnings.append("빈 줄이 과도하게 연속됩니다.")

    rendered = render_sections(tuple(sections))
    return LyricsValidationResult(
        valid=not errors,
        normalized_lyrics=rendered,
        sections=tuple(sections),
        warnings=tuple(dict.fromkeys(warnings)),
        errors=tuple(dict.fromkeys(errors)),
        character_count=len(rendered),
        line_count=len(lyric_lines),
        section_count=len(sections),
        repetition_ratio=round(repetition_ratio, 6),
    )


def render_sections(sections: tuple[LyricsSection, ...]) -> str:
    blocks = []
    for section in sections:
        label = section.section_type.replace("_", " ").title()
        blocks.append(f"[{label}]\n" + "\n".join(section.lines))
    return "\n\n".join(blocks)
