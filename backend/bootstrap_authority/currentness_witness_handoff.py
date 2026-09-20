"""Single-attempt CurrentnessWitness handoff; never admission or authorization.

The provider may issue one opaque witness only after an exact correlation and
the existing native lease/lifetime attempt are simultaneously revalidated.
The witness remains usable only inside that correlation context, lease and root
caller transaction.  No production port is exposed here.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from dataclasses import dataclass

from backend.bootstrap_authority.confirmation_lineage_correlation import (
    _ConfirmationLineageCorrelations,
)
from backend.bootstrap_authority.confirmation_lineage_correlation import (
    _Record as _CorrelationRecord,
)
from backend.bootstrap_authority.witness_lifetime import (
    CurrentnessBinding,
    WitnessLifetimeDenied,
    _Handle,
    _ProviderWitnessLifetime,
    _require_scope,
)


class CurrentnessWitnessHandoffDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("CURRENTNESS_WITNESS_HANDOFF_DENIED")


@dataclass(slots=True, repr=False)
class _WitnessRecord:
    attempt: _Handle
    witness: _Handle
    correlation_handle: _Handle
    correlation_record: _CorrelationRecord
    lease: object
    session: object
    transaction: object
    binding: CurrentnessBinding
    exact_scope: tuple[str, str, str]
    invalidated: bool = False


def _correlation_arguments(record):
    return {
        "authenticity_handle": record.authenticity_handle,
        "observation_handle": record.observation_handle,
        "confirmation_handle": record.confirmation_handle,
        "lineage_handle": record.lineage_handle,
        "material_handle": record.material_handle,
        "authority_handle": record.authority_handle,
        "designation_handle": record.designation_handle,
        "lease": record.lease,
        "session": record.session,
        "pin_facts": record.pin_facts,
        "fresh_action": record.action,
        "fresh_lineage": record.lineage,
        "expected_payload": record.expected_payload,
        "expected_material": record.expected_material,
        "expected_source": record.expected_source,
        "expected_scope": record.expected_scope,
        "signature_text": record.signature_text,
    }


class _CurrentnessWitnessHandoff:
    """Adapter-owned ephemeral witness issuance over an exact correlation."""

    def __init__(self, *, correlations, witness_lifetime):
        if (
            type(correlations) is not _ConfirmationLineageCorrelations
            or type(witness_lifetime) is not _ProviderWitnessLifetime
            or correlations._authenticity._confirmation._serialization._lifetime
            is not witness_lifetime
        ):
            raise CurrentnessWitnessHandoffDenied()
        self._correlations = correlations
        self._lifetime = witness_lifetime
        self._serialization = correlations._authenticity._confirmation._serialization
        self._records = {}

    def _preflight(self, *, attempt, correlation_handle, exact_scope, arguments):
        if type(attempt) is not _Handle or type(correlation_handle) is not _Handle:
            raise CurrentnessWitnessHandoffDenied()
        attempt_record = None
        correlation_record = None
        try:
            attempt_record = self._lifetime._lookup(attempt)
            correlation_record = self._correlations._records.get(correlation_handle)
            if type(correlation_record) is not _CorrelationRecord:
                raise CurrentnessWitnessHandoffDenied()
            binding = correlation_record.pin_facts.binding
            if type(binding) is not CurrentnessBinding:
                raise CurrentnessWitnessHandoffDenied()
            binding.__post_init__()
            _require_scope(exact_scope)
            if (
                attempt_record.witness is not None
                or attempt_record.lease is not correlation_record.lease
                or attempt_record.session is not correlation_record.session
                or attempt_record.transaction is not correlation_record.caller_transaction
                or attempt_record.binding != binding
                or exact_scope not in binding.affected_scopes
                or any(
                    arguments.get(name) is not value
                    for name, value in (
                        ("lease", correlation_record.lease),
                        ("session", correlation_record.session),
                        ("pin_facts", correlation_record.pin_facts),
                    )
                )
            ):
                raise CurrentnessWitnessHandoffDenied()
            self._serialization._require_live(
                correlation_record.lease,
                session=correlation_record.session,
                scopes=binding.affected_scopes,
            )
            self._correlations._require_open(correlation_handle, **arguments)
            repeated = self._lifetime._lookup(attempt)
            current = self._correlations._records.get(correlation_handle)
            if repeated is not attempt_record or current is not correlation_record:
                raise CurrentnessWitnessHandoffDenied()
            self._serialization._require_live(
                correlation_record.lease,
                session=correlation_record.session,
                scopes=binding.affected_scopes,
            )
            return attempt_record, correlation_record, binding
        except CurrentnessWitnessHandoffDenied:
            self._abandon_failed_preflight(
                attempt,
                correlation_handle,
                attempt_record=attempt_record,
                correlation_record=correlation_record,
            )
            raise
        except Exception:
            self._abandon_failed_preflight(
                attempt,
                correlation_handle,
                attempt_record=attempt_record,
                correlation_record=correlation_record,
            )
            raise CurrentnessWitnessHandoffDenied() from None

    def _abandon_failed_preflight(
        self,
        attempt,
        correlation_handle,
        *,
        attempt_record,
        correlation_record,
    ):
        """Reject only a proven same-chain attempt; foreign inputs have no kill authority."""
        if (
            type(correlation_record) is not _CorrelationRecord
            or attempt_record is None
            or attempt_record.witness is not None
            or attempt_record.lease is not correlation_record.lease
            or attempt_record.session is not correlation_record.session
            or attempt_record.transaction is not correlation_record.caller_transaction
            or type(correlation_record.pin_facts.binding) is not CurrentnessBinding
            or attempt_record.binding != correlation_record.pin_facts.binding
        ):
            return
        self._lifetime._reject_attempt(attempt, witness=None)
        self._correlations._abandon_all(
            handle=correlation_handle,
            **_correlation_arguments(correlation_record),
        )

    def _invalidate(self, record):
        if record is None or record.invalidated:
            return
        record.invalidated = True
        self._records.pop(record.witness, None)
        with suppress(WitnessLifetimeDenied):
            self._lifetime._reject_attempt(record.attempt, witness=record.witness)
        try:
            self._correlations._abandon_all(
                handle=record.correlation_handle,
                **_correlation_arguments(record.correlation_record),
            )
        except Exception:
            # The provider attempt is already quarantined above.  Cleanup loss
            # must surface as denial and can never restore the witness.
            raise CurrentnessWitnessHandoffDenied() from None

    @contextmanager
    def _open_witness(self, *, attempt, correlation_handle, exact_scope, **arguments):
        record = None
        registered = None
        try:
            attempt_record, correlation_record, binding = self._preflight(
                attempt=attempt,
                correlation_handle=correlation_handle,
                exact_scope=exact_scope,
                arguments=arguments,
            )
            try:
                registered = self._lifetime._register_after_independent_currentness(attempt)
            except WitnessLifetimeDenied:
                # Atomic single assignment owns issue/issue concurrency.  A losing
                # duplicate cannot invalidate the already-issued winner.
                live = self._lifetime._attempts.get(attempt)
                if live is attempt_record and live.witness is not None:
                    raise CurrentnessWitnessHandoffDenied() from None
                raise
            self._correlations._require_open(correlation_handle, **arguments)
            self._serialization._require_live(
                correlation_record.lease,
                session=correlation_record.session,
                scopes=binding.affected_scopes,
            )
            self._lifetime._require_live_binding(
                attempt=attempt,
                witness=registered,
                lease=correlation_record.lease,
                session=correlation_record.session,
                freshly_verified_binding=binding,
                exact_scope=exact_scope,
            )
            if self._correlations._records.get(correlation_handle) is not correlation_record:
                raise CurrentnessWitnessHandoffDenied()
            record = _WitnessRecord(
                attempt,
                registered,
                correlation_handle,
                correlation_record,
                correlation_record.lease,
                correlation_record.session,
                attempt_record.transaction,
                binding,
                exact_scope,
            )
            self._records[registered] = record
            try:
                yield registered
            finally:
                self._invalidate(record)
        except CurrentnessWitnessHandoffDenied:
            if registered is not None and record is None:
                transient = _WitnessRecord(
                    attempt,
                    registered,
                    correlation_handle,
                    correlation_record,
                    correlation_record.lease,
                    correlation_record.session,
                    attempt_record.transaction,
                    binding,
                    exact_scope,
                )
                self._invalidate(transient)
            raise
        except Exception:
            if registered is not None and record is None:
                transient = _WitnessRecord(
                    attempt,
                    registered,
                    correlation_handle,
                    correlation_record,
                    correlation_record.lease,
                    correlation_record.session,
                    attempt_record.transaction,
                    binding,
                    exact_scope,
                )
                self._invalidate(transient)
            raise CurrentnessWitnessHandoffDenied() from None

    def _require_current(self, witness, *, attempt, correlation_handle, exact_scope, **arguments):
        if type(witness) is not _Handle or witness not in self._records:
            raise CurrentnessWitnessHandoffDenied()
        record = self._records[witness]
        try:
            _require_scope(exact_scope)
            if (
                attempt is not record.attempt
                or correlation_handle is not record.correlation_handle
                or exact_scope != record.exact_scope
                or self._correlations._records.get(correlation_handle)
                is not record.correlation_record
            ):
                raise CurrentnessWitnessHandoffDenied()
            self._lifetime._require_live_binding(
                attempt=record.attempt,
                witness=record.witness,
                lease=record.lease,
                session=record.session,
                freshly_verified_binding=record.binding,
                exact_scope=record.exact_scope,
            )
            self._correlations._require_open(correlation_handle, **arguments)
            self._serialization._require_live(
                record.lease,
                session=record.session,
                scopes=record.binding.affected_scopes,
            )
            self._lifetime._require_live_binding(
                attempt=record.attempt,
                witness=record.witness,
                lease=record.lease,
                session=record.session,
                freshly_verified_binding=record.binding,
                exact_scope=record.exact_scope,
            )
        except Exception:
            self._invalidate(record)
            raise CurrentnessWitnessHandoffDenied() from None


__all__ = ["CurrentnessWitnessHandoffDenied"]
