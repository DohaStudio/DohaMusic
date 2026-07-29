"""Minimal Responses API HTTP client with sanitized provider errors."""

from __future__ import annotations

from typing import Protocol

import httpx

from backend.lyrics.providers.openai.exceptions import OpenAIProviderError


class OpenAITransport(Protocol):
    def create_response(
        self, payload: dict[str, object], timeout_seconds: float
    ) -> dict[str, object]: ...


class OpenAIResponsesClient:
    def __init__(self, *, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._endpoint = f"{base_url.rstrip('/')}/responses"

    def create_response(
        self, payload: dict[str, object], timeout_seconds: float
    ) -> dict[str, object]:
        try:
            response = httpx.post(
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise OpenAIProviderError("timeout", retryable=True) from exc
        except httpx.NetworkError as exc:
            raise OpenAIProviderError("unavailable", retryable=True) from exc

        provider_code = self._provider_code(response)
        if response.status_code == 429:
            raise OpenAIProviderError("rate_limited", retryable=True)
        if response.status_code in {500, 502, 503, 504}:
            raise OpenAIProviderError("unavailable", retryable=True)
        if response.status_code in {401, 403}:
            raise OpenAIProviderError("authentication")
        if response.status_code >= 400:
            if provider_code in {"content_policy_violation", "content_filter"}:
                raise OpenAIProviderError("content_blocked")
            raise OpenAIProviderError("request_rejected")
        try:
            data = response.json()
        except ValueError as exc:
            raise OpenAIProviderError("invalid_output") from exc
        if not isinstance(data, dict):
            raise OpenAIProviderError("invalid_output")
        return data

    @staticmethod
    def _provider_code(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
            return None
        code = payload["error"].get("code")
        return code if isinstance(code, str) else None
