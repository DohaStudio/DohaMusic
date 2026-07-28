"""Safe local storage layout for Backend Foundation."""

from __future__ import annotations

import wave
from pathlib import Path


class StorageService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.inputs_dir = self.root / "inputs"
        self.outputs_dir = self.root / "outputs"
        self.voices_dir = self.root / "voices"
        self.samples_dir = self.root / "samples"
        self.stems_dir = self.root / "stems"
        self.stem_vocals_dir = self.stems_dir / "vocals"
        self.stem_instrumentals_dir = self.stems_dir / "instrumentals"
        self.stem_metadata_dir = self.stems_dir / "metadata"
        self.sample_file = self.samples_dir / "sample.wav"

    def ensure_layout(self) -> None:
        for directory in (
            self.inputs_dir,
            self.outputs_dir,
            self.voices_dir,
            self.samples_dir,
            self.stem_vocals_dir,
            self.stem_instrumentals_dir,
            self.stem_metadata_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        if not self.sample_file.exists():
            self._write_silent_wav(self.sample_file)

    def relative_path(self, file_path: Path) -> str:
        resolved = file_path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("File must remain inside the configured storage root")
        return resolved.relative_to(self.root).as_posix()

    def resolve_relative_path(self, file_path: str) -> Path:
        resolved = (self.root / file_path).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("File must remain inside the configured storage root")
        return resolved

    @staticmethod
    def _write_silent_wav(file_path: Path) -> None:
        sample_rate = 8_000
        frame_count = sample_rate // 10
        with wave.open(str(file_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(sample_rate)
            audio.writeframes(b"\x00\x00" * frame_count)
