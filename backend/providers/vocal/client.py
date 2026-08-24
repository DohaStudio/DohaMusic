"""DohaVocal Runtime 9개 operation의 strict consumer client."""

from __future__ import annotations

import re
from typing import TypeVar
from urllib.parse import quote

from pydantic import BaseModel, TypeAdapter, ValidationError

from .contracts import (
    DOHAVOCAL_CONTRACT_VERSION,
    AnyVocalJob,
    BaseVocalJob,
    VocalCapabilities,
    VocalCreateJobRequest,
    VocalErrorEnvelope,
    VocalHealthProbe,
    VocalModelManifest,
    VocalProviderResultCandidate,
    VocalReadinessProbe,
)
from .errors import (
    VocalProviderApplicationError,
    VocalProviderContractVersionError,
    VocalProviderErrorDetail,
    VocalProviderInvalidResponseError,
    VocalProviderTimeoutError,
    VocalProviderTransportError,
)
from .transport import (
    VocalProviderTransport,
    VocalTransportRequest,
    VocalTransportResponse,
)

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
_JOB_ADAPTER = TypeAdapter(AnyVocalJob)
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_SAFE_TOKEN = re.compile(r"[A-Za-z0-9:._-]{1,128}\Z")
_UNSAFE_MESSAGE = re.compile(
    r"(?:traceback|api[_ -]?key|token|secret|[A-Za-z]:[\\/]|\\\\|/[^ ]+/[^ ]+)",
    flags=re.IGNORECASE,
)


class VocalProviderClient:
    """Provider source package나 DB에 의존하지 않는 consumer adapter."""

    def __init__(self, transport: VocalProviderTransport) -> None:
        self._transport = transport

    def get_capabilities(self) -> VocalCapabilities:
        return self._request("GET", "/v1/capabilities", VocalCapabilities)

    def create_job(self, request: VocalCreateJobRequest) -> BaseVocalJob:
        job = self._request_job(
            "POST",
            "/v1/jobs",
            expected_status=201,
            json_body=request.model_dump(mode="json"),
        )
        if (
            job.job_type != request.capability
            or job.model_manifest_id != request.model_manifest_id
            or job.input_asset_version_ids != request.input_asset_version_ids
            or job.input_artifact_ids != request.input_artifact_ids
            or job.settings_snapshot != request.settings_snapshot
        ):
            raise _invalid_response()
        return job

    def get_job_status(self, job_id: str) -> BaseVocalJob:
        job = self._request_job("GET", f"/v1/jobs/{_path_segment(job_id)}")
        if job.job_id != job_id:
            raise _invalid_response()
        return job

    def cancel_job(self, job_id: str) -> BaseVocalJob:
        job = self._request_job("POST", f"/v1/jobs/{_path_segment(job_id)}/cancel")
        if job.job_id != job_id:
            raise _invalid_response()
        return job

    def retry_job(self, job_id: str) -> BaseVocalJob:
        job = self._request_job("POST", f"/v1/jobs/{_path_segment(job_id)}/retry")
        if job.job_id == job_id or job.retry_of_job_id != job_id:
            raise _invalid_response()
        return job

    def get_result(self, job_id: str) -> VocalProviderResultCandidate:
        result = self._request(
            "GET",
            f"/v1/jobs/{_path_segment(job_id)}/result",
            VocalProviderResultCandidate,
        )
        if result.run_id != job_id or result.lineage.job_id != job_id:
            raise _invalid_response()
        return result

    def get_model_manifest(self, model_manifest_id: str) -> VocalModelManifest:
        manifest = self._request(
            "GET",
            f"/v1/model-manifests/{_path_segment(model_manifest_id)}",
            VocalModelManifest,
        )
        if manifest.model_manifest_id != model_manifest_id:
            raise _invalid_response()
        return manifest

    def health(self) -> bool:
        return self._request("GET", "/health", VocalHealthProbe).status == "ok"

    def readiness(self) -> bool:
        return self._request("GET", "/ready", VocalReadinessProbe).status == "ready"

    def _request_job(
        self,
        method: str,
        path: str,
        *,
        expected_status: int = 200,
        json_body: dict[str, object] | None = None,
    ) -> BaseVocalJob:
        response = self._send(method, path, json_body=json_body)
        payload = self._payload(response, expected_status)
        try:
            return _JOB_ADAPTER.validate_python(payload)
        except ValidationError:
            raise _invalid_response() from None

    def _request(
        self,
        method: str,
        path: str,
        model: type[ResponseModel],
        *,
        expected_status: int = 200,
    ) -> ResponseModel:
        response = self._send(method, path)
        payload = self._payload(response, expected_status)
        try:
            return model.model_validate(payload)
        except ValidationError:
            raise _invalid_response() from None

    def _send(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, object] | None = None,
    ) -> VocalTransportResponse:
        try:
            return self._transport.send(
                VocalTransportRequest(method=method, path=path, json_body=json_body)
            )
        except TimeoutError:
            raise VocalProviderTimeoutError(
                VocalProviderErrorDetail(
                    "PROVIDER_TIMEOUT",
                    "Vocal Provider 응답 시간이 초과되었습니다.",
                    True,
                    "transport",
                    "not-available",
                )
            ) from None
        except OSError:
            raise VocalProviderTransportError(
                VocalProviderErrorDetail(
                    "PROVIDER_TRANSPORT_ERROR",
                    "Vocal Provider에 연결할 수 없습니다.",
                    True,
                    "transport",
                    "not-available",
                )
            ) from None

    @staticmethod
    def _payload(response: VocalTransportResponse, expected_status: int) -> object:
        if not isinstance(response, VocalTransportResponse):
            raise _invalid_response()
        if response.status_code == expected_status:
            if (
                isinstance(response.json_body, dict)
                and "api_contract_version" in response.json_body
                and response.json_body["api_contract_version"] != DOHAVOCAL_CONTRACT_VERSION
            ):
                raise VocalProviderContractVersionError(
                    VocalProviderErrorDetail(
                        "PROVIDER_CONTRACT_VERSION_UNSUPPORTED",
                        "Vocal Provider contract version이 지원 기준과 다릅니다.",
                        False,
                        "response_validation",
                        "not-available",
                    )
                )
            return response.json_body
        if 200 <= response.status_code < 300:
            raise _invalid_response()
        try:
            provider_error = VocalErrorEnvelope.model_validate(response.json_body).error
        except ValidationError:
            raise _invalid_response() from None
        detail = _safe_error(provider_error)
        if detail.error_code in {
            "CONTRACT_VERSION_UNSUPPORTED",
            "PROVIDER_CONTRACT_VERSION_UNSUPPORTED",
        }:
            raise VocalProviderContractVersionError(detail)
        raise VocalProviderApplicationError(detail)


def _safe_error(error: object) -> VocalProviderErrorDetail:
    error_code = getattr(error, "error_code", "")
    stage = getattr(error, "stage", "")
    details_id = getattr(error, "details_id", "")
    message = getattr(error, "message", "")
    safe_code = error_code if _SAFE_CODE.fullmatch(error_code) else "PROVIDER_ERROR"
    safe_stage = stage if _SAFE_TOKEN.fullmatch(stage) else "provider"
    safe_details = details_id if _SAFE_TOKEN.fullmatch(details_id) else "not-available"
    safe_message = (
        message
        if isinstance(message, str)
        and 1 <= len(message) <= 300
        and "\n" not in message
        and _UNSAFE_MESSAGE.search(message) is None
        else "Vocal Provider 요청을 처리하지 못했습니다."
    )
    return VocalProviderErrorDetail(
        safe_code,
        safe_message,
        bool(getattr(error, "retryable", False)),
        safe_stage,
        safe_details,
    )


def _invalid_response() -> VocalProviderInvalidResponseError:
    return VocalProviderInvalidResponseError(
        VocalProviderErrorDetail(
            "PROVIDER_RESPONSE_INVALID",
            "Vocal Provider 응답 계약이 유효하지 않습니다.",
            False,
            "response_validation",
            "not-available",
        )
    )


def _path_segment(value: str) -> str:
    encoded = quote(value, safe="@")
    if encoded in {".", ".."}:
        return encoded.replace(".", "%2E")
    return encoded
