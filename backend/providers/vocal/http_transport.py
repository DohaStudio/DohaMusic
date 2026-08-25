"""Configuration-bound HTTP transport for the DohaVocal consumer contract."""

from __future__ import annotations

from hashlib import sha256
from types import TracebackType
from typing import TYPE_CHECKING, Self
from urllib.parse import quote, urlsplit

import httpx

from .acquisition import (
    VerifiedVocalPayload,
    VocalPayloadAcquisitionError,
    VocalPayloadAcquisitionErrorCode,
    VocalPayloadAcquisitionRequest,
)
from .errors import VocalProviderErrorDetail, VocalProviderInvalidResponseError
from .transport import VocalTransportRequest, VocalTransportResponse

if TYPE_CHECKING:
    from backend.core.config import Settings


class HttpVocalProviderTransport:
    """Reusable synchronous HTTP adapter with no automatic retry policy."""

    def __init__(
        self,
        *,
        base_url: str,
        connect_timeout_seconds: float = 2.0,
        read_timeout_seconds: float = 30.0,
        write_timeout_seconds: float = 10.0,
        pool_timeout_seconds: float = 2.0,
        payload_max_bytes: int = 64 * 1024 * 1024,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )
        if payload_max_bytes <= 0:
            raise ValueError("DohaVocal payload maximum must be positive")
        self._payload_max_bytes = payload_max_bytes
        self._client = client or httpx.Client(follow_redirects=False)
        self._owns_client = client is None
        self._closed = False

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
    ) -> HttpVocalProviderTransport:
        return cls(
            base_url=settings.dohavocal_base_url,
            connect_timeout_seconds=settings.dohavocal_connect_timeout_seconds,
            read_timeout_seconds=settings.dohavocal_read_timeout_seconds,
            write_timeout_seconds=settings.dohavocal_write_timeout_seconds,
            pool_timeout_seconds=settings.dohavocal_pool_timeout_seconds,
            payload_max_bytes=settings.dohavocal_payload_max_bytes,
            client=client,
        )

    @property
    def is_closed(self) -> bool:
        return self._closed

    def send(self, request: VocalTransportRequest) -> VocalTransportResponse:
        if self._closed:
            raise OSError("DohaVocal HTTP transport is closed")
        _validate_origin_relative_path(request.path)
        headers = dict(request.headers)
        headers["Accept"] = "application/json"
        kwargs: dict[str, object] = {
            "headers": headers,
            "timeout": self._timeout,
            "follow_redirects": False,
        }
        if request.json_body is not None:
            kwargs["json"] = dict(request.json_body)
        try:
            response = self._client.request(
                request.method,
                f"{self._base_url}{request.path}",
                **kwargs,
            )
        except httpx.TimeoutException:
            raise TimeoutError("DohaVocal HTTP request timed out") from None
        except httpx.RequestError:
            raise OSError("DohaVocal HTTP request failed") from None
        except RuntimeError:
            raise OSError("DohaVocal HTTP client is unavailable") from None

        if not _is_json_content_type(response.headers.get("content-type")):
            raise _invalid_http_response()
        try:
            payload = response.json()
        except ValueError:
            raise _invalid_http_response() from None
        return VocalTransportResponse(response.status_code, payload)

    def acquire_payload(
        self, request: VocalPayloadAcquisitionRequest
    ) -> VerifiedVocalPayload:
        """Stream one advertised provider subresource into bounded transient memory."""

        if self._closed:
            raise VocalPayloadAcquisitionError(
                VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED
            )
        payload = request.payload
        maximum_bytes = min(request.max_size_bytes, self._payload_max_bytes)
        if payload.expected_size_bytes > maximum_bytes:
            raise _payload_integrity_error()
        path = (
            f"/v1/jobs/{_payload_segment(request.job_id)}/artifacts/"
            f"{_payload_segment(payload.provider_artifact_id)}/payloads/"
            f"{_payload_segment(payload.source.source_id)}"
        )
        _validate_origin_relative_path(path)
        try:
            with self._client.stream(
                "GET",
                f"{self._base_url}{path}",
                headers={"Accept": payload.expected_media_type},
                timeout=self._timeout,
                follow_redirects=False,
            ) as response:
                _require_payload_status(response.status_code)
                media_type = _normalized_media_type(
                    response.headers.get("content-type")
                )
                if media_type != payload.expected_media_type:
                    raise _payload_integrity_error()
                declared_length = _content_length(
                    response.headers.get("content-length")
                )
                if declared_length is not None and (
                    declared_length != payload.expected_size_bytes
                    or declared_length > maximum_bytes
                ):
                    raise _payload_integrity_error()

                digest = sha256()
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > maximum_bytes or size > payload.expected_size_bytes:
                        raise _payload_integrity_error()
                    digest.update(chunk)
                    chunks.append(chunk)
        except VocalPayloadAcquisitionError:
            raise
        except httpx.TimeoutException:
            raise VocalPayloadAcquisitionError(
                VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED
            ) from None
        except (httpx.HTTPError, RuntimeError):
            raise VocalPayloadAcquisitionError(
                VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED
            ) from None

        if size != payload.expected_size_bytes:
            raise _payload_integrity_error()
        actual_checksum = digest.hexdigest()
        if actual_checksum != payload.payload_checksum:
            raise _payload_integrity_error()
        return VerifiedVocalPayload(
            job_id=request.job_id,
            provider_artifact_id=payload.provider_artifact_id,
            source_id=payload.source.source_id,
            media_type=media_type,
            size_bytes=size,
            checksum_algorithm="sha256",
            payload_checksum=actual_checksum,
            content=b"".join(chunks),
        )

    def close(self) -> None:
        if self._closed:
            return
        if self._owns_client:
            self._client.close()
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _normalize_base_url(value: str) -> str:
    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as error:
        raise ValueError("DohaVocal base URL is invalid") from error
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "DohaVocal base URL must be an HTTP(S) origin without userinfo"
        )
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("DohaVocal base URL port is invalid")
    return candidate.rstrip("/")


def _validate_origin_relative_path(path: str) -> None:
    parsed = urlsplit(path)
    if (
        not path.startswith("/")
        or path.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or any(segment in {".", ".."} for segment in parsed.path.split("/"))
    ):
        raise OSError("DohaVocal request path is invalid")


def _is_json_content_type(value: str | None) -> bool:
    if value is None:
        return False
    media_type = value.partition(";")[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _payload_segment(value: str) -> str:
    return quote(value, safe="")


def _normalized_media_type(value: str | None) -> str:
    if value is None:
        raise _payload_integrity_error()
    return value.partition(";")[0].strip().lower()


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        raise _payload_integrity_error() from None
    if parsed < 0:
        raise _payload_integrity_error()
    return parsed


def _require_payload_status(status_code: int) -> None:
    if status_code == 200:
        return
    if status_code in {401, 403}:
        code = VocalPayloadAcquisitionErrorCode.PAYLOAD_ACCESS_DENIED
    elif status_code == 404:
        code = VocalPayloadAcquisitionErrorCode.PAYLOAD_UNAVAILABLE
    elif status_code == 410:
        code = VocalPayloadAcquisitionErrorCode.PAYLOAD_EXPIRED
    else:
        code = VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED
    raise VocalPayloadAcquisitionError(code)


def _payload_integrity_error() -> VocalPayloadAcquisitionError:
    return VocalPayloadAcquisitionError(
        VocalPayloadAcquisitionErrorCode.PAYLOAD_INTEGRITY_MISMATCH
    )


def _invalid_http_response() -> VocalProviderInvalidResponseError:
    return VocalProviderInvalidResponseError(
        VocalProviderErrorDetail(
            "PROVIDER_RESPONSE_INVALID",
            "Vocal Provider HTTP 응답을 안전하게 해석할 수 없습니다.",
            False,
            "response_validation",
            "not-available",
        )
    )
