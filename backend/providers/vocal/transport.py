"""DohaVocal 호출을 실제 network 구현과 분리하는 transport port."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class VocalTransportRequest:
    method: str
    path: str
    json_body: Mapping[str, Any] | None = None
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VocalTransportResponse:
    status_code: int
    json_body: Any


class VocalProviderTransport(Protocol):
    """HTTP·ASGI·subprocess 세부 구현을 consumer에서 숨기는 port."""

    def send(self, request: VocalTransportRequest) -> VocalTransportResponse: ...
