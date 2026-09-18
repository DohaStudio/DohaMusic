"""Fixed raw designation-record snapshot mechanics, NOT authentic designation.

No governance/human/ACL proof or new signed designation wire. No witness issuance.
Even live snapshot + currentness lifetime comparison is NOT admission permission.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PinComparisonFacts, PrivateFactsDenied
from backend.bootstrap_authority.private_pin_reader import _PrivatePinFactsReader
from backend.bootstrap_authority.source_custody import (
    SourceCustodyPolicy,
    _CustodyDesignationRecordFiles,
)
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.bootstrap_authority.windows_serialization import CeremonySerializationDenied
from backend.bootstrap_authority.witness_lifetime import (
    _MINT,
    CurrentnessBinding,
    WitnessLifetimeDenied,
    _Handle,
)

DESIGNATION_RECORD_FILE = "designation-record-v1.txt"


class _DesignationRecordFiles(_WindowsFactFiles):
    # Trusted internal component, never a caller-selectable filename.
    _fixed_name = DESIGNATION_RECORD_FILE


@dataclass(slots=True, repr=False)
class _Snapshot:
    lease: object
    session: Session
    pin_facts: PinComparisonFacts
    binding: CurrentnessBinding
    native_lease: object


class _DesignationRecordSnapshots:
    """Reviewed composition injects fixed root; no production factory/port.

    Opaque handles only describe a live, matching raw record snapshot. Independent
    custody/authenticity/human acceptance/revocation checks are STILL unavailable.
    """

    def __init__(
        self,
        *,
        trusted_root: str,
        pin_reader: _PrivatePinFactsReader,
        custody_policy: SourceCustodyPolicy | None = None,
    ):
        if type(pin_reader) is not _PrivatePinFactsReader:
            raise PrivateFactsDenied()
        self._pin = pin_reader
        self._serialization = pin_reader._serialization
        # Legacy raw mechanics stay NON-authorizing. Strict policy path is also
        # partial evidence: no designated human/current eligibility is inferred.
        self._files = (
            _DesignationRecordFiles(trusted_root)
            if custody_policy is None
            else _CustodyDesignationRecordFiles(trusted_root, custody_policy)
        )
        self._snapshots: dict[_Handle, _Snapshot] = {}

    def _abandon(self, handle: object, record: _Snapshot) -> None:
        self._snapshots.pop(handle, None)
        record.native_lease.invalid = True
        self._serialization._lifetime._release_lease(record.lease)

    @contextmanager
    def _open_record(self, *, lease: object, session: Session, pin_facts: PinComparisonFacts):
        try:
            original = self._serialization._lookup(lease)
            try:
                self._serialization._require_live(lease, session=session, scopes=original.scopes)
                self._pin._require_open_facts(pin_facts, lease=lease, session=session)
                if type(pin_facts) is not PinComparisonFacts:
                    raise PrivateFactsDenied()
                with self._files._snapshot() as raw:
                    # Exact bytes, no JCS/Unicode normalization of external record.
                    text = raw.decode("utf-8", errors="strict")
                    if not text.strip() or "\x00" in text or text.startswith("\ufeff"):
                        raise PrivateFactsDenied()
                    if digest(raw) != pin_facts.binding.designation_record_digest:
                        raise PrivateFactsDenied()
                    self._pin._require_open_facts(pin_facts, lease=lease, session=session)
                    handle = _Handle(_MINT)
                    record = _Snapshot(lease, session, pin_facts, pin_facts.binding, original)
                    self._snapshots[handle] = record
                    try:
                        yield handle
                    finally:
                        self._abandon(handle, record)
            finally:
                # Malformed expectations/source/context failure cannot revive witnesses.
                original.invalid = True
                self._serialization._lifetime._release_lease(lease)
        except (OSError, UnicodeError, CeremonySerializationDenied, WitnessLifetimeDenied):
            raise PrivateFactsDenied() from None

    def _require_current_snapshot(
        self,
        handle: object,
        *,
        attempt: object,
        witness: object,
        freshly_verified_binding: CurrentnessBinding,
        exact_scope: tuple[str, str, str],
    ) -> None:
        """Necessary identity/lifetime comparison ONLY; not currentness verification.

        Trusted adapter must supply independently issued currentness witness. This
        module never registers one. Production ports remain unavailable.
        """
        if type(handle) is not _Handle or handle not in self._snapshots:
            raise PrivateFactsDenied()
        record = self._snapshots[handle]
        try:
            self._pin._require_open_facts(
                record.pin_facts, lease=record.lease, session=record.session
            )
            if type(self._files) is _CustodyDesignationRecordFiles:
                self._files._require_unchanged()
            if type(freshly_verified_binding) is not CurrentnessBinding:
                raise PrivateFactsDenied()
            freshly_verified_binding.__post_init__()
            if freshly_verified_binding != record.binding:
                raise PrivateFactsDenied()
            self._serialization._lifetime._require_live_binding(
                attempt=attempt,
                witness=witness,
                lease=record.lease,
                session=record.session,
                freshly_verified_binding=freshly_verified_binding,
                exact_scope=exact_scope,
            )
        except (PrivateFactsDenied, WitnessLifetimeDenied, CeremonySerializationDenied):
            self._abandon(handle, record)
            raise PrivateFactsDenied() from None

    def _require_open_snapshot(self, handle, *, lease, session, pin_facts) -> None:
        """Original live partial snapshot ONLY; no authentication/witness check.

        Used by another raw snapshot inside this held context. Public facts/copies
        cannot substitute the original provider's identity. Denial abandons it.
        """
        if type(handle) is not _Handle or handle not in self._snapshots:
            raise PrivateFactsDenied()
        record = self._snapshots[handle]
        try:
            if (
                record.lease is not lease
                or record.session is not session
                or record.pin_facts is not pin_facts
            ):
                raise PrivateFactsDenied()
            self._pin._require_open_facts(pin_facts, lease=lease, session=session)
            if type(self._files) is _CustodyDesignationRecordFiles:
                record.binding.__post_init__()
                self._files._require_same_bytes(record.binding.designation_record_digest)
        except (PrivateFactsDenied, WitnessLifetimeDenied, CeremonySerializationDenied):
            self._abandon(handle, record)
            raise PrivateFactsDenied() from None
