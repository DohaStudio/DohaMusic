"""Subprocess bridge to the isolated official Demucs environment."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from backend.ai.adapters.demucs.config import DemucsConfig
from backend.ai.errors import (
    StemAudioDecodeError,
    StemDependencyNotInstalledError,
    StemInferenceError,
    StemModelLoadError,
    StemModelNotFoundError,
    StemOutOfMemoryError,
    StemOutputNotCreatedError,
    StemProviderNotConfiguredError,
    StemSeparationError,
    StemTimeoutError,
)


@dataclass(frozen=True, slots=True)
class DemucsRuntimeResult:
    vocals_path: Path
    instrumental_path: Path
    metadata_path: Path
    duration_seconds: float
    separation_time_seconds: float
    peak_vram_mb: float | None
    peak_process_memory_mb: float | None


ERROR_TYPES: dict[str, type[StemSeparationError]] = {
    "STEM_PROVIDER_NOT_CONFIGURED": StemProviderNotConfiguredError,
    "STEM_DEPENDENCY_NOT_INSTALLED": StemDependencyNotInstalledError,
    "STEM_MODEL_NOT_FOUND": StemModelNotFoundError,
    "STEM_MODEL_LOAD_FAILED": StemModelLoadError,
    "STEM_SEPARATION_FAILED": StemInferenceError,
    "STEM_OUT_OF_MEMORY": StemOutOfMemoryError,
    "STEM_OUTPUT_NOT_CREATED": StemOutputNotCreatedError,
    "STEM_AUDIO_DECODE_FAILED": StemAudioDecodeError,
    "STEM_TIMEOUT": StemTimeoutError,
}


class SubprocessDemucsRuntime:
    def __init__(self, config: DemucsConfig) -> None:
        self.config = config

    def separate(self, source_path: Path, job_id: str) -> DemucsRuntimeResult:
        self.config.validate()
        paths = self._output_paths(job_id)
        try:
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StemOutputNotCreatedError("Stem 출력 디렉터리를 준비할 수 없습니다.") from exc
        command = [
            str(self.config.runtime_python),
            str(self.config.runner_path),
            "--input-path",
            str(source_path),
            "--vocals-output",
            str(paths["vocals"]),
            "--instrumental-output",
            str(paths["instrumental"]),
            "--metadata-path",
            str(paths["metadata"]),
            "--work-dir",
            str(paths["work"]),
            "--model-name",
            self.config.model_name,
            "--model-version",
            self.config.model_version,
            "--device",
            self.config.device,
            "--segment-seconds",
            str(self.config.segment_seconds),
            "--shifts",
            str(self.config.shifts),
            "--overlap",
            str(self.config.overlap),
            "--model-cache-path",
            str(self.config.model_cache_path),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                timeout=self.config.timeout_seconds,
                env=self._environment(),
            )
        except subprocess.TimeoutExpired as exc:
            raise StemTimeoutError("Stem 분리 제한 시간을 초과했습니다.") from exc
        except OSError as exc:
            raise StemDependencyNotInstalledError(
                "Demucs 격리 runtime을 실행할 수 없습니다."
            ) from exc
        payload = self._read_payload(completed.stdout, paths["metadata"])
        if completed.returncode != 0 or not payload.get("success"):
            self._raise_failure(payload)
        return DemucsRuntimeResult(
            vocals_path=paths["vocals"],
            instrumental_path=paths["instrumental"],
            metadata_path=paths["metadata"],
            duration_seconds=float(payload["duration_actual"]),
            separation_time_seconds=float(payload["separation_time_seconds"]),
            peak_vram_mb=_optional_float(payload.get("peak_nvidia_smi_mb")),
            peak_process_memory_mb=_optional_float(payload.get("process_memory_peak_mb")),
        )

    def _output_paths(self, job_id: str) -> dict[str, Path]:
        return {
            "vocals": (self.config.stem_root / "vocals" / f"{job_id}.wav").resolve(),
            "instrumental": (self.config.stem_root / "instrumentals" / f"{job_id}.wav").resolve(),
            "metadata": (self.config.stem_root / "metadata" / f"{job_id}.json").resolve(),
            "work": (self.config.stem_root / "work" / job_id).resolve(),
        }

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HF_HOME": str(self.config.model_cache_path),
                "HF_HUB_OFFLINE": "1",
                "DO_NOT_TRACK": "1",
            }
        )
        return environment

    @staticmethod
    def _read_payload(stdout: str, metadata_path: Path) -> dict[str, object]:
        if metadata_path.is_file():
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise StemInferenceError("Demucs runner가 결과를 반환하지 않았습니다.")
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise StemInferenceError("Demucs runner 결과 형식이 유효하지 않습니다.") from exc

    @staticmethod
    def _raise_failure(payload: dict[str, object]) -> None:
        code = str(payload.get("error_code", "STEM_SEPARATION_FAILED"))
        error_type = ERROR_TYPES.get(code, StemInferenceError)
        message = str(payload.get("error_message", "Stem 분리에 실패했습니다."))
        raise error_type(message)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)
