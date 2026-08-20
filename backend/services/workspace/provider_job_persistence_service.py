"""Workspace Job ↔ Provider Job durable binding application contract."""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    ApplicationValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.models.workspace.provider_job import ProviderJobBinding
from backend.repositories.workspace import JobRepository, ProviderJobRepository

MAX_PROVIDER_ID_LENGTH = 128
MAX_PROVIDER_JOB_ID_LENGTH = 256
_PROVIDER_ID = re.compile(r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?")
_PROVIDER_JOB_ID = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?")
_URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_SENSITIVE_ID_TEXT = re.compile(
    r"(?:authorization|bearer|api[_-]?key|credential|password|secret|token)",
    re.IGNORECASE,
)


class ProviderJobPersistenceErrorReason(StrEnum):
    INVALID_PROVIDER_ID = "invalid_provider_id"
    INVALID_PROVIDER_JOB_ID = "invalid_provider_job_id"
    JOB_PROVIDER_MISMATCH = "job_provider_mismatch"
    RETRY_SELF_REFERENCE = "retry_self_reference"
    RETRY_PARENT_NOT_FOUND = "retry_parent_not_found"
    RETRY_CROSS_WORKSPACE = "retry_cross_workspace"
    RETRY_CROSS_PROVIDER = "retry_cross_provider"


class ProviderJobPersistenceError(ApplicationValidationError):
    """호출자가 retry/identity 실패 원인을 구조적으로 구분할 수 있는 오류."""

    def __init__(self, reason: ProviderJobPersistenceErrorReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class ProviderJobPersistenceService:
    """Owner-scoped Provider Job identity history를 transaction 단위로 관리한다."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def create_binding_for_owner(
        self,
        *,
        effective_owner_id: UUID,
        workspace_job_id: UUID,
        provider_id: str,
        provider_job_id: str,
        retry_of_provider_job_id: str | None = None,
    ) -> ProviderJobBinding:
        normalized_provider = _normalize_provider_id(provider_id)
        normalized_job_id = _normalize_provider_job_id(provider_job_id)
        normalized_retry_id = (
            _normalize_provider_job_id(retry_of_provider_job_id)
            if retry_of_provider_job_id is not None
            else None
        )
        if normalized_retry_id == normalized_job_id:
            raise ProviderJobPersistenceError(
                ProviderJobPersistenceErrorReason.RETRY_SELF_REFERENCE,
                "Provider Job은 자기 자신을 retry parent로 참조할 수 없습니다.",
            )

        try:
            with self.session_factory() as session, session.begin():
                job = JobRepository(session).get_job_for_owner(
                    workspace_job_id, effective_owner_id
                )
                if job is None:
                    raise ResourceNotFoundError("Workspace Job")
                if job.provider_id != normalized_provider:
                    raise ProviderJobPersistenceError(
                        ProviderJobPersistenceErrorReason.JOB_PROVIDER_MISMATCH,
                        "Workspace Job과 Provider Job의 Provider ID가 일치해야 합니다.",
                    )

                repository = ProviderJobRepository(session)
                if normalized_retry_id is not None:
                    self._validate_retry_parent(
                        repository,
                        workspace_job_id=workspace_job_id,
                        provider_id=normalized_provider,
                        retry_of_provider_job_id=normalized_retry_id,
                    )
                return repository.add_binding(
                    ProviderJobBinding(
                        workspace_job_id=workspace_job_id,
                        provider_id=normalized_provider,
                        provider_job_id=normalized_job_id,
                        retry_of_provider_job_id=normalized_retry_id,
                    )
                )
        except IntegrityError as error:
            raise ResourceConflictError("Provider Job identity") from error

    def list_bindings_for_owner(
        self,
        *,
        effective_owner_id: UUID,
        workspace_job_id: UUID,
        limit: int = 100,
    ) -> tuple[ProviderJobBinding, ...]:
        _validate_limit(limit)
        with self.session_factory() as session, session.begin():
            self._require_owned_job(session, workspace_job_id, effective_owner_id)
            bindings = ProviderJobRepository(session).list_by_workspace_job(
                workspace_job_id, limit=limit
            )
            return tuple(bindings)

    def get_latest_binding_for_owner(
        self,
        *,
        effective_owner_id: UUID,
        workspace_job_id: UUID,
    ) -> ProviderJobBinding | None:
        with self.session_factory() as session, session.begin():
            self._require_owned_job(session, workspace_job_id, effective_owner_id)
            return ProviderJobRepository(session).get_latest_for_workspace_job(
                workspace_job_id
            )

    @staticmethod
    def _require_owned_job(
        session: Session, workspace_job_id: UUID, effective_owner_id: UUID
    ) -> None:
        if (
            JobRepository(session).get_job_for_owner(
                workspace_job_id, effective_owner_id
            )
            is None
        ):
            raise ResourceNotFoundError("Workspace Job")

    @staticmethod
    def _validate_retry_parent(
        repository: ProviderJobRepository,
        *,
        workspace_job_id: UUID,
        provider_id: str,
        retry_of_provider_job_id: str,
    ) -> None:
        parent = repository.get_by_provider_identity(
            provider_id, retry_of_provider_job_id
        )
        if parent is None:
            other_provider_bindings = repository.find_by_provider_job_id(
                retry_of_provider_job_id
            )
            if other_provider_bindings:
                raise ProviderJobPersistenceError(
                    ProviderJobPersistenceErrorReason.RETRY_CROSS_PROVIDER,
                    "Provider retry parent는 같은 Provider에 속해야 합니다.",
                )
            raise ProviderJobPersistenceError(
                ProviderJobPersistenceErrorReason.RETRY_PARENT_NOT_FOUND,
                "Provider retry parent binding을 찾을 수 없습니다.",
            )
        if parent.workspace_job_id != workspace_job_id:
            raise ProviderJobPersistenceError(
                ProviderJobPersistenceErrorReason.RETRY_CROSS_WORKSPACE,
                "Provider retry parent는 같은 Workspace Job에 속해야 합니다.",
            )


def _normalize_provider_id(value: object) -> str:
    if not isinstance(value, str):
        raise ProviderJobPersistenceError(
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_ID,
            "Provider ID는 logical identifier여야 합니다.",
        )
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > MAX_PROVIDER_ID_LENGTH
        or _PROVIDER_ID.fullmatch(normalized) is None
    ):
        raise ProviderJobPersistenceError(
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_ID,
            "Provider ID는 안전한 소문자 logical identifier여야 합니다.",
        )
    return normalized


def _normalize_provider_job_id(value: object) -> str:
    if not isinstance(value, str):
        raise ProviderJobPersistenceError(
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_JOB_ID,
            "Provider Job ID는 logical identifier여야 합니다.",
        )
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > MAX_PROVIDER_JOB_ID_LENGTH
        or _PROVIDER_JOB_ID.fullmatch(normalized) is None
        or _URI_SCHEME.match(normalized) is not None
        or _SENSITIVE_ID_TEXT.search(normalized) is not None
    ):
        raise ProviderJobPersistenceError(
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_JOB_ID,
            "Provider Job ID는 경로, URL, 비밀 또는 raw payload가 아닌 "
            "opaque ID여야 합니다.",
        )
    return normalized


def _validate_limit(limit: object) -> None:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ApplicationValidationError("limit은 1에서 100 사이의 정수여야 합니다.")
