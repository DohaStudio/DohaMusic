"""Flush-only ADR-075 fact primitives, never an authenticated Rights Writer.

All writes participate in the caller's transaction. A failed primitive requires
the caller to abandon the whole attempt; this module never retries or ends it.
Guard proof is transaction-local integrity bookkeeping, not authorization.
"""

from contextlib import contextmanager
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError, StatementError
from sqlalchemy.orm import Session

from backend.core.vocal_rights import (
    VocalRightsOperation,
    VocalRightsPersistenceError,
    VocalRightsSubjectType,
    VocalRightsUsageRole,
)
from backend.db.vocal_rights_schema_v1 import MAX_TOKEN
from backend.models.workspace import Artifact, Asset, AssetVersion, Workspace
from backend.models.workspace.vocal_rights import (
    VocalCompletionRightsReceipt,
    VocalCompletionRightsReceiptItem,
    VocalRightsCurrentAuthority,
    VocalRightsEvent,
    VocalRightsEvidence,
    VocalRightsEvidenceGuard,
    VocalRightsEvidenceScope,
    VocalRightsEvidenceWithdrawal,
    VocalRightsGrant,
    VocalRightsScopeGuard,
    VocalRightsSubject,
)


class VocalRightsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @contextmanager
    def _write(self):
        if self.session.get_bind().dialect.name != "sqlite":
            raise VocalRightsPersistenceError("AUTHORITY_UNAVAILABLE")
        if not self.session.in_transaction() or self.session.in_nested_transaction():
            raise VocalRightsPersistenceError("AUTHORITY_UNAVAILABLE")
        try:
            if self.session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
                raise VocalRightsPersistenceError("AUTHORITY_UNAVAILABLE")
            yield
        except IntegrityError:
            raise VocalRightsPersistenceError() from None
        except OperationalError:
            raise VocalRightsPersistenceError("AUTHORITY_UNAVAILABLE") from None
        except (StatementError, ValueError, TypeError):
            raise VocalRightsPersistenceError() from None

    def _fresh(self, model, *predicates):
        return self.session.scalar(
            select(model).where(*predicates).execution_options(populate_existing=True)
        )

    def _locks(self) -> dict:
        transaction = self.session.get_transaction()
        state = self.session.info.get("vocal_rights_guard_locks")
        if state is None or state["transaction"] is not transaction:
            state = {"transaction": transaction, "evidence": set(), "scope": set(), "last": None}
            self.session.info["vocal_rights_guard_locks"] = state
        return state

    def _held(self, evidence_ids: set[UUID], scope_ids: set[UUID]) -> None:
        state = self._locks()
        if not evidence_ids <= state["evidence"] or not scope_ids <= state["scope"]:
            raise VocalRightsPersistenceError("AUTHORITY_UNAVAILABLE")

    def get_scope_guard(self, owner_id: UUID, workspace_id: UUID):
        return self._fresh(
            VocalRightsScopeGuard,
            VocalRightsScopeGuard.owner_id == owner_id,
            VocalRightsScopeGuard.workspace_id == workspace_id,
        )

    def ensure_scope_guard(self, owner_id: UUID, workspace_id: UUID):
        """Empty anchor only. A racing unique loser must restart its caller Tx."""
        with self._write():
            guard = self.get_scope_guard(owner_id, workspace_id)
            if guard is not None:
                return guard
            workspace = self._fresh(Workspace, Workspace.workspace_id == workspace_id)
            if workspace is None or workspace.owner_id != owner_id:
                raise VocalRightsPersistenceError()
            guard = VocalRightsScopeGuard(owner_id=owner_id, workspace_id=workspace_id)
            self.session.add(guard)
            self.session.flush()
            return guard

    def conditional_guard_update(self, kind: str, guard_id: UUID, expected_epoch: int):
        """Real UPDATE, rowcount=1, write lock retained until caller Tx ends.

        Evidence UUID order precedes (workspace UUID, owner UUID) scope order.
        The lock token is not a semantic revision and never issues a Grant.
        """
        with self._write():
            if not 0 <= expected_epoch < MAX_TOKEN:
                raise VocalRightsPersistenceError()
            state = self._locks()
            if kind == "evidence":
                model, key = VocalRightsEvidenceGuard, VocalRightsEvidenceGuard.evidence_id
                order = (0, guard_id.hex, "")
            elif kind == "scope":
                model, key = VocalRightsScopeGuard, VocalRightsScopeGuard.scope_guard_id
                guard = self._fresh(model, key == guard_id)
                if guard is None:
                    raise VocalRightsPersistenceError()
                order = (1, guard.workspace_id.hex, guard.owner_id.hex)
            else:
                raise VocalRightsPersistenceError()
            if guard_id not in state[kind] and state["last"] is not None and order < state["last"]:
                raise VocalRightsPersistenceError("AUTHORITY_UNAVAILABLE")
            result = self.session.execute(
                update(model)
                .where(key == guard_id, model.guard_epoch == expected_epoch)
                .values(guard_epoch=model.guard_epoch + 1)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise VocalRightsPersistenceError()
            state[kind].add(guard_id)
            state["last"] = max(order, state["last"] or order)
            return self._fresh(model, key == guard_id)

    def ensure_current_authority(
        self,
        scope_guard_id: UUID,
        subject_type: VocalRightsSubjectType,
        subject_id: UUID,
        operation: VocalRightsOperation,
        usage_role: VocalRightsUsageRole,
    ):
        """Provision an empty exact key under a held stable anchor, not a grant."""
        with self._write():
            self._held(set(), {scope_guard_id})
            subject_type = VocalRightsSubjectType(subject_type)
            operation = VocalRightsOperation(operation)
            usage_role = VocalRightsUsageRole(usage_role)
            guard = self._fresh(
                VocalRightsScopeGuard, VocalRightsScopeGuard.scope_guard_id == scope_guard_id
            )
            workspace = self._fresh(Workspace, Workspace.workspace_id == guard.workspace_id)
            if workspace is None or workspace.owner_id != guard.owner_id:
                raise VocalRightsPersistenceError()
            target_column = {
                VocalRightsSubjectType.WORKSPACE: "workspace_id",
                VocalRightsSubjectType.ASSET_VERSION: "asset_version_id",
                VocalRightsSubjectType.ARTIFACT: "artifact_id",
            }[subject_type]
            if subject_type == VocalRightsSubjectType.WORKSPACE:
                matches = subject_id == guard.workspace_id
            else:
                version_id = subject_id
                if subject_type == VocalRightsSubjectType.ARTIFACT:
                    artifact = self._fresh(Artifact, Artifact.artifact_id == subject_id)
                    version_id = artifact.asset_version_id if artifact is not None else None
                version = self._fresh(AssetVersion, AssetVersion.asset_version_id == version_id)
                asset = (
                    self._fresh(Asset, Asset.asset_id == version.asset_id)
                    if version is not None
                    else None
                )
                matches = (
                    asset is not None
                    and asset.owner_id == guard.owner_id
                    and asset.workspace_id == guard.workspace_id
                )
            if not matches:
                raise VocalRightsPersistenceError()
            subject = self._fresh(
                VocalRightsSubject,
                VocalRightsSubject.subject_type == subject_type,
                VocalRightsSubject.subject_id == subject_id,
            )
            if subject is None:
                self.session.add(
                    VocalRightsSubject(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        **{target_column: subject_id},
                    )
                )
                self.session.flush()
            current = self._fresh(
                VocalRightsCurrentAuthority,
                VocalRightsCurrentAuthority.scope_guard_id == scope_guard_id,
                VocalRightsCurrentAuthority.subject_type == subject_type,
                VocalRightsCurrentAuthority.subject_id == subject_id,
                VocalRightsCurrentAuthority.operation == operation,
                VocalRightsCurrentAuthority.usage_role == usage_role,
            )
            if current is None:
                current = VocalRightsCurrentAuthority(
                    scope_guard_id=scope_guard_id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    operation=operation,
                    usage_role=usage_role,
                )
                self.session.add(current)
                self.session.flush()
            return current

    def read_current(self, authority_id: UUID):
        """Raw current facts only; ownership/evidence/permission are not approved."""
        return self._fresh(
            VocalRightsCurrentAuthority, VocalRightsCurrentAuthority.authority_id == authority_id
        )

    def append_evidence(self, evidence: VocalRightsEvidence, authority_ids: set[UUID]):
        """Persist caller-verified immutable facts; no verification is performed."""
        with self._write():
            if not authority_ids:
                raise VocalRightsPersistenceError()
            authorities = [self.read_current(key) for key in authority_ids]
            if any(authority is None for authority in authorities):
                raise VocalRightsPersistenceError()
            self._held(set(), {authority.scope_guard_id for authority in authorities})
            ordered_ids = sorted(authority_ids, key=lambda value: value.hex)
            evidence.scope_count = len(ordered_ids)
            evidence.last_scope_authority_id = ordered_ids[-1]
            evidence.last_scope_ordinal = len(ordered_ids) - 1
            self.session.add(evidence)
            self.session.flush()
            self.session.add(VocalRightsEvidenceGuard(evidence_id=evidence.evidence_id))
            for ordinal, key in enumerate(ordered_ids):
                self.session.add(
                    VocalRightsEvidenceScope(
                        evidence_id=evidence.evidence_id,
                        authority_id=key,
                        ordinal=ordinal,
                    )
                )
                self.session.flush()
            return evidence

    def append_transition(
        self,
        event: VocalRightsEvent,
        *,
        expected_revision: int,
        issuance: VocalRightsGrant | None = None,
    ):
        """Append supplied facts atomically; no grant/revoke/supersede policy API.

        SQLite event trigger CAS-checks the fresh previous pointer/revision and
        advances projection by exactly one. Old and new evidence locks required.
        """
        with self._write():
            current = self.read_current(event.authority_id)
            if (
                current is None
                or current.semantic_revision != expected_revision
                or event.semantic_revision != expected_revision + 1
            ):
                raise VocalRightsPersistenceError()
            if current.current_grant_id != event.old_grant_id:
                raise VocalRightsPersistenceError()
            if (event.new_grant_id is not None) != (issuance is not None):
                raise VocalRightsPersistenceError()
            evidence_ids = set()
            if event.old_grant_id is not None:
                old = self._fresh(VocalRightsGrant, VocalRightsGrant.grant_id == event.old_grant_id)
                evidence_ids.add(old.evidence_id)
            if issuance is not None:
                if (
                    issuance.authority_id != event.authority_id
                    or issuance.grant_id != event.new_grant_id
                ):
                    raise VocalRightsPersistenceError()
                evidence_ids.add(issuance.evidence_id)
            self._held(evidence_ids, {current.scope_guard_id})
            if issuance is not None:
                self.session.add(issuance)
                self.session.flush()
            self.session.add(event)
            self.session.flush()
            return self.read_current(event.authority_id)

    def list_events(self, authority_id: UUID):
        return list(
            self.session.scalars(
                select(VocalRightsEvent)
                .where(VocalRightsEvent.authority_id == authority_id)
                .order_by(VocalRightsEvent.semantic_revision)
            )
        )

    def append_withdrawal_fact(self, event: VocalRightsEvidenceWithdrawal):
        """Fact primitive only; connected Grant revocation orchestration excluded."""
        with self._write():
            authorities = list(
                self.session.scalars(
                    select(VocalRightsCurrentAuthority)
                    .join(
                        VocalRightsEvidenceScope,
                        VocalRightsEvidenceScope.authority_id
                        == VocalRightsCurrentAuthority.authority_id,
                    )
                    .where(VocalRightsEvidenceScope.evidence_id == event.evidence_id)
                )
            )
            self._held({event.evidence_id}, {authority.scope_guard_id for authority in authorities})
            self.session.add(event)
            self.session.flush()

    def append_receipt(
        self, receipt: VocalCompletionRightsReceipt, items: list[VocalCompletionRightsReceiptItem]
    ):
        """Final aggregate fact only, not a Completion hook or replay permission.

        Caller owns output writes and authority validation. All item guards must
        still be held; keys are sorted without deduplicating distinct roles.
        """
        with self._write():
            if not items or len({item.authority_id for item in items}) != len(items):
                raise VocalRightsPersistenceError()
            authorities = {
                item.authority_id: self.read_current(item.authority_id) for item in items
            }
            if any(authority is None for authority in authorities.values()):
                raise VocalRightsPersistenceError()
            self._held(
                {item.evidence_id for item in items},
                {authority.scope_guard_id for authority in authorities.values()},
            )
            scopes = {
                authority.scope_guard_id: self._fresh(
                    VocalRightsScopeGuard,
                    VocalRightsScopeGuard.scope_guard_id == authority.scope_guard_id,
                )
                for authority in authorities.values()
            }

            def key(item):
                authority = authorities[item.authority_id]
                scope = scopes[authority.scope_guard_id]
                return (
                    scope.owner_id.hex,
                    scope.workspace_id.hex,
                    authority.subject_type,
                    authority.subject_id.hex,
                    authority.operation,
                    authority.usage_role,
                )

            items = sorted(items, key=key)
            receipt.receipt_id = receipt.receipt_id or uuid4()
            receipt.item_count = len(items)
            receipt.last_ordinal = len(items) - 1
            for ordinal, item in enumerate(items):
                item.item_id = item.item_id or uuid4()
                item.receipt_id = receipt.receipt_id
                item.ordinal = ordinal
            receipt.last_item_id = items[-1].item_id
            self.session.add(receipt)
            self.session.flush()
            for item in items:
                self.session.add(item)
                self.session.flush()
            return receipt
