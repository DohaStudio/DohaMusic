"""Subprocess bridge to the isolated official ACE-Step environment."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.ai.adapters.ace_step.config import AceStepConfig
from backend.ai.errors import (
    AIAudioDecodeError,
    AIDependencyNotInstalledError,
    AIInferenceError,
    AIModelLoadError,
    AIModelNotFoundError,
    AIOutOfMemoryError,
    AIOutputNotCreatedError,
    AIProviderNotConfiguredError,
    AITimeoutError,
    MusicGenerationError,
)


@dataclass(frozen=True, slots=True)
class AceStepRuntimeResult:
    audio_path: Path
    metadata_path: Path
    duration_seconds: float
    generation_time_seconds: float
    peak_vram_mb: float | None
    seed: int | None


ERROR_TYPES: dict[str, type[MusicGenerationError]] = {
    "AI_PROVIDER_NOT_CONFIGURED": AIProviderNotConfiguredError,
    "AI_DEPENDENCY_NOT_INSTALLED": AIDependencyNotInstalledError,
    "AI_MODEL_NOT_FOUND": AIModelNotFoundError,
    "AI_MODEL_LOAD_FAILED": AIModelLoadError,
    "AI_INFERENCE_FAILED": AIInferenceError,
    "AI_OUT_OF_MEMORY": AIOutOfMemoryError,
    "AI_OUTPUT_NOT_CREATED": AIOutputNotCreatedError,
    "AI_AUDIO_DECODE_FAILED": AIAudioDecodeError,
    "AI_TIMEOUT": AITimeoutError,
}


class SubprocessAceStepRuntime:
    def __init__(self, config: AceStepConfig) -> None:
        self.config = config

    def generate(self, request: dict[str, object], job_id: str) -> AceStepRuntimeResult:
        self.config.validate()
        output_dir = (self.config.output_root / job_id).resolve()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AIOutputNotCreatedError("ACE-Step 출력 디렉터리를 준비할 수 없습니다.") from exc
        metadata_path = output_dir / "metadata.json"
        request_path = self._write_request(output_dir, request)
        try:
            completed = subprocess.run(
                [
                    str(self.config.runtime_python),
                    str(self.config.runner_path),
                    "--request-json",
                    str(request_path),
                    "--output-dir",
                    str(output_dir),
                    "--metadata-path",
                    str(metadata_path),
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.config.timeout_seconds,
                env=self._environment(),
            )
        except subprocess.TimeoutExpired as exc:
            raise AITimeoutError("ACE-Step 추론 제한 시간을 초과했습니다.") from exc
        except OSError as exc:
            raise AIDependencyNotInstalledError(
                "ACE-Step 격리 runtime을 실행할 수 없습니다."
            ) from exc
        finally:
            request_path.unlink(missing_ok=True)

        payload = self._read_payload(completed.stdout, metadata_path)
        if completed.returncode != 0 or not payload.get("success"):
            self._raise_failure(payload)
        relative_audio = Path(str(payload["output_path"]))
        audio_path = (output_dir / relative_audio).resolve()
        return AceStepRuntimeResult(
            audio_path=audio_path,
            metadata_path=metadata_path,
            duration_seconds=float(payload["duration_actual"]),
            generation_time_seconds=float(payload["inference_time_seconds"]),
            peak_vram_mb=_optional_float(payload.get("nvidia_smi_peak_used_vram_mb")),
            seed=_optional_int(payload.get("seed")),
        )

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        values = {
            "DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT": self.config.project_root,
            "DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH": self.config.checkpoint_path,
            "DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT": self.config.model_variant,
            "DOHAMUSIC_AI_ACE_STEP_MODEL_VERSION": self.config.model_version,
            "DOHAMUSIC_AI_ACE_STEP_DEVICE": self.config.device,
            "DOHAMUSIC_AI_ACE_STEP_QUANTIZATION": self.config.quantization or "",
            "DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD": str(self.config.cpu_offload).lower(),
            "DOHAMUSIC_AI_ACE_STEP_DIT_CPU_OFFLOAD": str(self.config.dit_cpu_offload).lower(),
        }
        environment.update({key: str(value) for key, value in values.items()})
        return environment

    @staticmethod
    def _write_request(output_dir: Path, request: dict[str, object]) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="request-",
            dir=output_dir,
            delete=False,
            encoding="utf-8",
        ) as request_file:
            json.dump(request, request_file, ensure_ascii=False)
            return Path(request_file.name)

    @staticmethod
    def _read_payload(stdout: str, metadata_path: Path) -> dict[str, object]:
        if metadata_path.is_file():
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise AIInferenceError("ACE-Step runner가 결과를 반환하지 않았습니다.")
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise AIInferenceError("ACE-Step runner 결과 형식이 유효하지 않습니다.") from exc

    @staticmethod
    def _raise_failure(payload: dict[str, object]) -> None:
        code = str(payload.get("error_code", "AI_INFERENCE_FAILED"))
        error_type = ERROR_TYPES.get(code, AIInferenceError)
        message = str(payload.get("error_message", "ACE-Step 추론에 실패했습니다."))
        raise error_type(message)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)
