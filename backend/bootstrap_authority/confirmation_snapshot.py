"""Raw original-confirmation live snapshot mechanics, NOT source authentication.

No signed confirmation wire/issuer verifier/human acceptance/current-lineage
reader, currentness/admission witness or production port. File/ACL/digest equality
is NOT authentic confirmation; production composition remains unavailable.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from backend.bootstrap_authority.designation_snapshot import _DesignationRecordSnapshots
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.private_pin_reader import _PrivatePinFactsReader
from backend.bootstrap_authority.provisioning_binding import (
    ProvisioningBindingDenied,
    action_comparison_digest,
    require_action_binding,
    require_current_lineage_matches,
)
from backend.bootstrap_authority.source_custody import (
    SourceCustodyPolicy,
    _CustodyDesignationRecordFiles,
)
from backend.bootstrap_authority.windows_serialization import CeremonySerializationDenied
from backend.bootstrap_authority.witness_lifetime import _MINT, WitnessLifetimeDenied, _Handle

CONFIRMATION_RECORD_FILE = "original-confirmation-v1.txt"


def _lineage_key(lineage):
    require_current_lineage_matches(observed=lineage, expected=lineage)
    return (
        lineage.anchor_id,
        lineage.installation_id,
        lineage.source_id,
        lineage.statuses,
        tuple(action_comparison_digest(action) for action in lineage.actions),
    )


class _ConfirmationFiles(_CustodyDesignationRecordFiles):
    _fixed_name = CONFIRMATION_RECORD_FILE


@dataclass(slots=True, repr=False)
class _Record:
    lease: object
    session: object
    pin_facts: object
    designation: object
    action: object
    lineage: object
    lineage_key: tuple
    action_digest: str
    native_lease: object


class _OriginalConfirmationSnapshots:
    """Reviewed-injected snapshot helper, not authentic provenance observation.

    Explicit separate expected confirmation file identity never comes from the
    observed descriptor. Existing designation custody and live pin are mandatory.
    """

    def __init__(self, *, trusted_root, pin_reader, designation_snapshots, confirmation_policy):
        if (
            type(pin_reader) is not _PrivatePinFactsReader
            or type(designation_snapshots) is not _DesignationRecordSnapshots
            or designation_snapshots._pin is not pin_reader
            or type(designation_snapshots._files) is not _CustodyDesignationRecordFiles
            or type(confirmation_policy) is not SourceCustodyPolicy
        ):
            raise PrivateFactsDenied()
        self._pin, self._designation = pin_reader, designation_snapshots
        self._serialization = pin_reader._serialization
        self._files = _ConfirmationFiles(trusted_root, confirmation_policy)
        if not (
            self._files._paths == pin_reader._files._paths == designation_snapshots._files._paths
        ):
            raise PrivateFactsDenied()
        policy = designation_snapshots._files._policy
        if (
            confirmation_policy.root_identity != policy.root_identity
            or confirmation_policy.record_identity == policy.record_identity
            or confirmation_policy.owner_sid != policy.owner_sid
            or confirmation_policy.allowed_sids != policy.allowed_sids
            or confirmation_policy.dacl != policy.dacl
        ):
            raise PrivateFactsDenied()
        self._records: dict[_Handle, _Record] = {}

    def _abandon(self, handle, record):
        self._records.pop(handle, None)
        record.native_lease.invalid = True
        self._serialization._lifetime._release_lease(record.lease)

    def _require_inputs(self, *, lease, session, pin_facts, designation, action, lineage):
        self._designation._require_open_snapshot(
            designation, lease=lease, session=session, pin_facts=pin_facts
        )
        action_comparison_digest(action)
        require_current_lineage_matches(observed=lineage, expected=lineage)
        if lineage.actions[-1] != action:
            raise PrivateFactsDenied()
        require_action_binding(
            action=action, policy=action.policy, pin=pin_facts, confirmation=action.confirmation
        )
        if action.policy.custody != self._designation._files._policy:
            raise PrivateFactsDenied()

    @contextmanager
    def _open_snapshot(self, *, lease, session, pin_facts, designation, action, lineage):
        try:
            original = self._serialization._lookup(lease)
            try:
                self._require_inputs(
                    lease=lease,
                    session=session,
                    pin_facts=pin_facts,
                    designation=designation,
                    action=action,
                    lineage=lineage,
                )
                with self._files._snapshot() as raw:
                    text = raw.decode("utf-8", errors="strict")
                    if not text.strip() or "\x00" in text or text.startswith("\ufeff"):
                        raise PrivateFactsDenied()
                    if digest(raw) != action.confirmation.original_confirmation_digest:
                        raise PrivateFactsDenied()
                    self._require_inputs(
                        lease=lease,
                        session=session,
                        pin_facts=pin_facts,
                        designation=designation,
                        action=action,
                        lineage=lineage,
                    )
                    self._files._require_same_bytes(digest(raw))
                    handle = _Handle(_MINT)
                    record = _Record(
                        lease,
                        session,
                        pin_facts,
                        designation,
                        action,
                        lineage,
                        _lineage_key(lineage),
                        action_comparison_digest(action),
                        original,
                    )
                    self._records[handle] = record
                    try:
                        yield handle
                    finally:
                        self._abandon(handle, record)
            finally:
                original.invalid = True
                self._serialization._lifetime._release_lease(lease)
        except (
            OSError,
            UnicodeError,
            TypeError,
            AttributeError,
            ProvisioningBindingDenied,
            CeremonySerializationDenied,
            WitnessLifetimeDenied,
        ):
            raise PrivateFactsDenied() from None

    def _require_unchanged(self, handle, *, fresh_action, fresh_lineage):
        """Caller MUST independently fresh-read/authenticate the semantic inputs.

        Comparing these public values and live raw bytes still grants NO authority.
        Observed mismatch permanently abandons original handle and lease usability.
        """
        if type(handle) is not _Handle or handle not in self._records:
            raise PrivateFactsDenied()
        record = self._records[handle]
        try:
            self._require_inputs(
                lease=record.lease,
                session=record.session,
                pin_facts=record.pin_facts,
                designation=record.designation,
                action=fresh_action,
                lineage=fresh_lineage,
            )
            require_current_lineage_matches(observed=fresh_lineage, expected=record.lineage)
            if _lineage_key(fresh_lineage) != record.lineage_key:
                raise PrivateFactsDenied()
            if action_comparison_digest(fresh_action) != record.action_digest:
                raise PrivateFactsDenied()
            self._files._require_same_bytes(record.action.confirmation.original_confirmation_digest)
        except Exception:
            # Even unexpected API errors cannot leave a reusable original record.
            self._abandon(handle, record)
            raise PrivateFactsDenied() from None
