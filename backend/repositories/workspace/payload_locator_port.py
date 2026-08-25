"""Persistence port for the durable PayloadLocator aggregate."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from backend.core.payload_locator import (
    PayloadLocatorIssue,
    PayloadLocatorRecord,
    PayloadLocatorStatus,
)


class PayloadLocatorRepositoryPort(Protocol):
    def issue(
        self,
        issue: PayloadLocatorIssue,
        *,
        locator_uuid: UUID,
    ) -> PayloadLocatorRecord: ...

    def get_by_locator_uuid(self, locator_uuid: UUID) -> PayloadLocatorRecord | None: ...

    def get_for_binding(
        self, provider_job_binding_id: UUID
    ) -> tuple[PayloadLocatorRecord, ...]: ...

    def get_by_binding_and_ordinal(
        self, provider_job_binding_id: UUID, payload_ordinal: int
    ) -> PayloadLocatorRecord | None: ...

    def compare_and_set(
        self,
        locator_uuid: UUID,
        *,
        expected_revision: int,
        expected_status: PayloadLocatorStatus,
        require_not_revoked: bool,
        values: dict[str, object],
    ) -> PayloadLocatorRecord: ...


class PayloadLocatorPersistencePort(Protocol):
    def transaction(self) -> AbstractContextManager[PayloadLocatorRepositoryPort]: ...
