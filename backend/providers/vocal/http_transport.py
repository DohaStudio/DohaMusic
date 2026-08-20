"""Configuration-bound HTTP transport for the DohaVocal consumer contract."""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Self
from urllib.parse import urlsplit

import httpx

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
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )
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
