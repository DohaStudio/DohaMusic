"""단일 HTTP byte Range 파싱 계약."""

from __future__ import annotations

import re
from dataclasses import dataclass

_RANGE_PATTERN = re.compile(r"^bytes=([0-9]*)-([0-9]*)$")


class RangeNotSatisfiable(ValueError):
    """Range 문법이 잘못됐거나 현재 Payload 크기로 만족할 수 없다."""


@dataclass(frozen=True, slots=True)
class ByteRange:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_single_byte_range(value: str | None, *, size_bytes: int) -> ByteRange | None:
    """지원하는 단일 byte Range를 inclusive start/end로 정규화한다."""

    if value is None:
        return None
    if type(value) is not str or type(size_bytes) is not int or size_bytes < 0:
        raise RangeNotSatisfiable
    if value != value.strip() or any(character.isspace() for character in value):
        raise RangeNotSatisfiable
    if "," in value:
        raise RangeNotSatisfiable

    match = _RANGE_PATTERN.fullmatch(value)
    if match is None:
        raise RangeNotSatisfiable
    first, last = match.groups()
    if not first and not last:
        raise RangeNotSatisfiable
    if size_bytes == 0:
        raise RangeNotSatisfiable

    if not first:
        suffix_length = int(last)
        if suffix_length <= 0:
            raise RangeNotSatisfiable
        return ByteRange(start=max(size_bytes - suffix_length, 0), end=size_bytes - 1)

    start = int(first)
    if start >= size_bytes:
        raise RangeNotSatisfiable
    if not last:
        return ByteRange(start=start, end=size_bytes - 1)

    requested_end = int(last)
    if requested_end < start:
        raise RangeNotSatisfiable
    return ByteRange(start=start, end=min(requested_end, size_bytes - 1))
