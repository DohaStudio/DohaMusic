"""DohaVocal consumer에서 외부로 안전하게 전달할 수 있는 오류."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VocalProviderErrorDetail:
    """원문 응답이나 내부 예외를 보존하지 않는 안전한 오류 projection."""

    error_code: str
    message: str
    retryable: bool
    stage: str
    details_id: str


class VocalProviderConsumerError(RuntimeError):
    """모든 DohaVocal consumer 오류의 안전한 기반 형식."""

    def __init__(self, detail: VocalProviderErrorDetail) -> None:
        super().__init__(detail.message)
        self.detail = detail


class VocalProviderApplicationError(VocalProviderConsumerError):
    """Provider가 구조화해 반환한 application 오류."""


class VocalProviderTransportError(VocalProviderConsumerError):
    """Provider에 도달하지 못한 transport 오류."""


class VocalProviderTimeoutError(VocalProviderTransportError):
    """Provider transport deadline 초과."""


class VocalProviderInvalidResponseError(VocalProviderConsumerError):
    """응답이 현재 consumer 계약으로 해석될 수 없음."""


class VocalProviderContractVersionError(VocalProviderConsumerError):
    """Provider contract version이 지원 기준과 다름."""
