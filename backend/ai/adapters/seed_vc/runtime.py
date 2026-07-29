"""Subprocess bridge to an isolated, pinned Seed-VC checkout."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from backend.ai.adapters.seed_vc.config import SeedVCConfig
from backend.ai.errors import (
    VoiceConversionError,
    VoiceDependencyNotInstalledError,
    VoiceInferenceError,
    VoiceModelLoadError,
    VoiceOutOfMemoryError,
    VoiceOutputNotCreatedError,
    VoiceTimeoutError,
)


@dataclass(frozen=True, slots=True)
class SeedVCRuntimeResult:
    converted_path: Path
    metadata_path: Path
    duration_seconds: float
    conversion_time_seconds: float
    peak_vram_mb: float | None
    peak_process_memory_mb: float | None


ERROR_TYPES: dict[str, type[VoiceConversionError]] = {
    "VOICE_DEPENDENCY_NOT_INSTALLED": VoiceDependencyNotInstalledError,
    "VOICE_MODEL_LOAD_FAILED": VoiceModelLoadError,
    "VOICE_CONVERSION_FAILED": VoiceInferenceError,
    "VOICE_OUT_OF_MEMORY": VoiceOutOfMemoryError,
    "VOICE_OUTPUT_NOT_CREATED": VoiceOutputNotCreatedError,
    "VOICE_TIMEOUT": VoiceTimeoutError,
}


class SubprocessSeedVCRuntime:
    def __init__(self, config: SeedVCConfig) -> None:
        self.config = config

    def convert(
        self, source_path: Path, reference_path: Path, job_id: str
    ) -> SeedVCRuntimeResult:
        self.config.validate()
        output = (self.config.voice_root / "converted" / f"{job_id}.wav").resolve()
        metadata = (self.config.voice_root / "metadata" / f"{job_id}.json").resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        output.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)
        command = [
            str(self.config.runtime_python),
            str(self.config.runner_path),
            "--project-root", str(self.config.project_root),
            "--source-path", str(source_path),
            "--reference-path", str(reference_path),
            "--output-path", str(output),
            "--metadata-path", str(metadata),
            "--checkpoint-path", str(self.config.checkpoint_path),
            "--config-path", str(self.config.config_path),
            "--model-name", self.config.model_name,
            "--model-version", self.config.model_version,
            "--device", self.config.device,
            "--diffusion-steps", str(self.config.diffusion_steps),
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
            raise VoiceTimeoutError("Voice Conversion 제한 시간을 초과했습니다.") from exc
        except OSError as exc:
            raise VoiceDependencyNotInstalledError(
                "Seed-VC 격리 runtime을 실행할 수 없습니다."
            ) from exc
        payload = self._read_payload(completed.stdout, metadata)
        if completed.returncode != 0 or not payload.get("success"):
            self._raise_failure(payload)
        return SeedVCRuntimeResult(
            converted_path=output,
            metadata_path=metadata,
            duration_seconds=float(payload["output_duration_seconds"]),
            conversion_time_seconds=float(payload["conversion_time_seconds"]),
            peak_vram_mb=_optional_float(payload.get("peak_vram_mb")),
            peak_process_memory_mb=_optional_float(
                payload.get("peak_process_memory_mb")
            ),
        )

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HF_HOME": str(self.config.model_cache_path),
                "HF_HUB_CACHE": str(self.config.model_cache_path / "hub"),
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "DO_NOT_TRACK": "1",
            }
        )
        return environment

    @staticmethod
    def _read_payload(stdout: str, metadata: Path) -> dict[str, object]:
        if metadata.is_file():
            return json.loads(metadata.read_text(encoding="utf-8"))
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise VoiceInferenceError("Seed-VC runner가 결과를 반환하지 않았습니다.")
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise VoiceInferenceError(
                "Seed-VC runner 결과 형식이 유효하지 않습니다."
            ) from exc

    @staticmethod
    def _raise_failure(payload: dict[str, object]) -> None:
        code = str(payload.get("error_code", "VOICE_CONVERSION_FAILED"))
        error_type = ERROR_TYPES.get(code, VoiceInferenceError)
        raise error_type(str(payload.get("error_message", "Voice Conversion 실패")))


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)
