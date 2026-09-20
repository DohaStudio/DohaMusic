"""ADR-080 provider-INTERNAL handle bookkeeping, never an authority provider.

Only a reviewed adapter, AFTER independent evidence/OS lease/fresh journal checks,
may use these internal methods. This module cannot establish those checks and is
not connected to any production port. Public binding equality is NOT permission.
The RLock serializes bookkeeping only, NOT a cross-process ceremony mutex.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from sqlalchemy.orm import Session, SessionTransaction

from backend.bootstrap_authority.contracts import (
    require_digest,
    require_reference,
    require_revision,
    require_uuid,
)
from backend.bootstrap_authority.journal_repository import JournalHead
from backend.bootstrap_authority.lifecycle_verifier import SCHEMA, digest


class WitnessLifetimeDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("DEPLOYMENT_WITNESS_LIFETIME_DENIED")


def _require_scope(scope: object) -> None:
    try:
        if type(scope) is not tuple or len(scope) != 3:
            raise ValueError("SCOPE")
        for value in scope:
            if type(value) is not str:
                raise ValueError("SCOPE")
            require_uuid(value)
    except (TypeError, ValueError):
        raise WitnessLifetimeDenied() from None


@dataclass(frozen=True, slots=True)
class CurrentnessBinding:
    """Strict immutable PUBLIC comparison value, NOT trusted provenance/currentness."""

    journal: JournalHead
    installed_pin: JournalHead
    designation_id: str
    designation_record_digest: str
    deployment_owner_ref: str
    affected_scopes: tuple[tuple[str, str, str], ...]
    root_key_id: str
    root_fingerprint: str
    root_public_key: bytes = field(repr=False)
    status: str = "ACTIVE_ISSUANCE"
    domain: str = SCHEMA

    def __post_init__(self) -> None:
        try:
            self._validate()
        except (ValueError, TypeError, AttributeError):
            raise WitnessLifetimeDenied() from None

    def _validate(self) -> None:
        if type(self.journal) is not JournalHead or type(self.installed_pin) is not JournalHead:
            raise ValueError("HEAD")
        head = self.journal
        for value in (
            self.designation_id,
            self.designation_record_digest,
            self.deployment_owner_ref,
            self.root_key_id,
            self.root_fingerprint,
            self.status,
            self.domain,
        ):
            if type(value) is not str:
                raise ValueError("PUBLIC_PRIMITIVE")
        # bool/float compare equal to integer 1 in Python. Validate BOTH stores,
        # not just the journal followed by dataclass equality against the pin.
        for projection in (head, self.installed_pin):
            if any(
                type(value) is not str
                for value in (
                    projection.journal_id,
                    projection.head_digest,
                    projection.current_key_id,
                    projection.last_key_id,
                )
            ):
                raise ValueError("PUBLIC_PRIMITIVE")
            require_uuid(projection.journal_id)
            require_revision(projection.revision)
            require_revision(projection.trust_revision)
            require_digest(projection.head_digest)
        require_reference(self.root_key_id)
        if (
            head.trust_revision != head.revision
            or head.current_key_id != self.root_key_id
            or head.last_key_id != self.root_key_id
            or self.installed_pin != head
            or self.status != "ACTIVE_ISSUANCE"
            or self.domain != SCHEMA
        ):
            raise ValueError("CURRENT_PROJECTION")
        require_uuid(self.designation_id)
        require_digest(self.designation_record_digest)
        require_reference(self.deployment_owner_ref)
        require_digest(self.root_fingerprint)
        if (
            type(self.root_public_key) is not bytes
            or len(self.root_public_key) != 32
            or digest(self.root_public_key) != self.root_fingerprint
        ):
            raise ValueError("FINGERPRINT")
        scopes = self.affected_scopes
        if type(scopes) is not tuple or not 0 < len(scopes) <= 4096:
            raise ValueError("MANIFEST")
        for scope in scopes:
            _require_scope(scope)
        if scopes != tuple(sorted(set(scopes))):
            raise ValueError("MEMBERSHIP")


_MINT = object()


class _Handle:
    __slots__ = ()

    def __new__(cls, mint=None):
        if mint is not _MINT:
            raise WitnessLifetimeDenied()
        return super().__new__(cls)

    def __init_subclass__(cls, **kwargs):
        raise TypeError("OPAQUE_HANDLE")

    def __copy__(self):
        raise TypeError("OPAQUE_HANDLE")

    def __deepcopy__(self, memo):
        raise TypeError("OPAQUE_HANDLE")

    def __reduce_ex__(self, protocol):
        raise TypeError("OPAQUE_HANDLE")

    def __repr__(self):
        return "<opaque deployment handle>"


@dataclass(slots=True, repr=False)
class _Attempt:
    lease: object
    session: Session
    transaction: SessionTransaction
    binding: CurrentnessBinding
    witness: _Handle | None = None


class _ProviderWitnessLifetime:
    """Adapter-owned lifetime checks only; no read/admit/commit/install/authorize API.

    Internal registration does NOT verify independent provenance. No concrete
    production adapter uses this helper. Test fixtures exercise mechanics only;
    UnavailableCurrentnessPorts remains the sole production concrete composition.
    No Session commit/rollback/flush, SQL, hidden retry or journal/pin writes.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._attempts: dict[_Handle, _Attempt] = {}
        # Retain identity references: no caller __eq__/__hash__ or id reuse.
        self._used_leases: dict[int, object] = {}
        self._closed = False

    @staticmethod
    def _root_transaction(session: Session) -> SessionTransaction:
        if not isinstance(session, Session) or session.get_nested_transaction() is not None:
            raise WitnessLifetimeDenied()
        transaction = session.get_transaction()
        if transaction is None or not transaction.is_active:
            raise WitnessLifetimeDenied()
        return transaction

    def _begin_after_verified_lease(
        self, *, lease: object, session: Session, binding: CurrentnessBinding
    ) -> object:
        """Trusted adapter must already have checked lease provenance/complete scope.

        One ceremony attempt per lease; release/retry requires a fresh lease.
        Savepoint-bound attempts are unsupported and fail closed, never unlocked.
        """
        with self._lock:
            if self._closed or lease is None or id(lease) in self._used_leases:
                raise WitnessLifetimeDenied()
            if type(binding) is not CurrentnessBinding:
                raise WitnessLifetimeDenied()
            binding.__post_init__()
            transaction = self._root_transaction(session)
            attempt = _Handle(_MINT)
            self._attempts[attempt] = _Attempt(lease, session, transaction, binding)
            self._used_leases[id(lease)] = lease
            return attempt

    def _register_after_independent_currentness(self, attempt: object) -> object:
        """Called ONLY after provider independently verifies pin/journal/provenance.

        This call is not that verification and cannot produce admission authority.
        Registration is single-assignment, avoiding replacement/reactivation.
        """
        with self._lock:
            record = self._lookup(attempt)
            try:
                self._require_transaction(record)
            except WitnessLifetimeDenied:
                self._attempts.pop(attempt)
                raise
            if record.witness is not None:
                raise WitnessLifetimeDenied()
            record.witness = _Handle(_MINT)
            return record.witness

    def _lookup(self, attempt: object) -> _Attempt:
        # Exact type + registry membership/identity, NOT isinstance alone.
        if self._closed or type(attempt) is not _Handle or attempt not in self._attempts:
            raise WitnessLifetimeDenied()
        return self._attempts[attempt]

    def _require_transaction(self, record: _Attempt) -> None:
        if self._root_transaction(record.session) is not record.transaction:
            raise WitnessLifetimeDenied()

    def _require_live_binding(
        self,
        *,
        attempt: object,
        witness: object,
        lease: object,
        session: Session,
        freshly_verified_binding: CurrentnessBinding,
        exact_scope: tuple[str, str, str],
    ) -> None:
        """Necessary lifetime check, NEVER sufficient for require_current permission.

        Fresh independent reader/OS lease checks must happen in the trusted adapter,
        inside its actual ceremony lease. Caller equality cannot supply freshness.
        """
        with self._lock:
            record = self._lookup(attempt)
            try:
                self._require_transaction(record)
                if type(freshly_verified_binding) is not CurrentnessBinding:
                    raise WitnessLifetimeDenied()
                freshly_verified_binding.__post_init__()
                _require_scope(exact_scope)
                if (
                    record.witness is None
                    or witness is not record.witness
                    or lease is not record.lease
                    or session is not record.session
                    or freshly_verified_binding != record.binding
                    or exact_scope not in record.binding.affected_scopes
                ):
                    raise WitnessLifetimeDenied()
            except WitnessLifetimeDenied:
                # Abandon the whole attempt. A matching old snapshot/savepoint
                # end must never reactivate a handle after observed invalidation.
                self._attempts.pop(attempt)
                raise

    def _release_lease(self, lease: object) -> None:
        """Provider calls on actual lease release; old identity can never reopen."""
        with self._lock:
            self._used_leases[id(lease)] = lease
            self._attempts = {
                handle: record
                for handle, record in self._attempts.items()
                if record.lease is not lease
            }

    def _reject_attempt(self, attempt: object, *, witness: object | None) -> None:
        """Permanently reject one exact attempt without pretending to release its OS lease."""
        with self._lock:
            if type(attempt) is not _Handle:
                raise WitnessLifetimeDenied()
            record = self._attempts.get(attempt)
            if record is None:
                return
            if witness is not None and record.witness is not witness:
                raise WitnessLifetimeDenied()
            self._attempts.pop(attempt, None)

    def _close(self) -> None:
        """Provider shutdown/restart abandons all handles; no persistence/import."""
        with self._lock:
            self._closed = True
            self._attempts.clear()
