"""Held authenticity/live-lineage/journal correlation, never currentness.

This internal foundation proves only that three already-held results describe the
same exact authority lineage while both caller-owned transactions and the native
ceremony lease remain live.  It neither mints a CurrentnessWitness nor admits a
request.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields

import rfc8785
from sqlalchemy.orm import SessionTransaction

from backend.bootstrap_authority.confirmation_authenticity import (
    _OriginalConfirmationAuthenticity,
)
from backend.bootstrap_authority.confirmation_payload import ExpectedConfirmationPayload
from backend.bootstrap_authority.confirmation_snapshot import _lineage_key
from backend.bootstrap_authority.fresh_journal_lineage import (
    _FreshJournalLineageObservations,
    _JournalSnapshot,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.provisioning_authority import (
    ExpectedProvisioningAuthorityScope,
)
from backend.bootstrap_authority.provisioning_authority_source import (
    ExpectedProvisioningAuthoritySource,
)
from backend.bootstrap_authority.provisioning_binding import (
    PolicyLineageFacts,
    ProvisioningActionFacts,
    action_comparison_digest,
    lineage_comparison_digest,
)
from backend.bootstrap_authority.provisioning_verifier_material import (
    ExpectedProvisioningVerifierMaterial,
)
from backend.bootstrap_authority.witness_lifetime import _MINT, _Handle


class ConfirmationLineageCorrelationDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("CONFIRMATION_LINEAGE_CORRELATION_DENIED")


@dataclass(frozen=True, slots=True, repr=False)
class _CorrelatedFacts:
    confirmation_id: str
    action_id: str
    policy_digest: str
    designation_digest: str
    initializer_ref: str
    replay_id: str
    installation_id: str
    producer_ref: str
    lineage_anchor_id: str
    lineage_source_id: str
    authenticity_lineage_digest: str
    live_lineage_digest: str
    lineage_record_digest: str
    head_action_digest: str
    predecessor_digest: str | None
    semantic_revision: int
    journal_id: str
    journal_revision: int
    journal_trust_revision: int
    journal_head_digest: str
    verifier_key_id: str
    verifier_fingerprint: str
    authority_source_id: str
    authority_source_revision: int
    authority_revision: int
    authority_head_digest: str
    material_id: str
    material_revision: int
    payload_digest: str
    signature_digest: str


@dataclass(slots=True, repr=False)
class _Record:
    authenticity_handle: _Handle
    observation_handle: _Handle
    confirmation_handle: _Handle
    lineage_handle: _Handle
    material_handle: _Handle
    authority_handle: _Handle
    designation_handle: _Handle
    lease: object
    session: object
    caller_transaction: SessionTransaction
    journal_transaction: SessionTransaction
    pin_facts: object
    expected_payload: ExpectedConfirmationPayload
    expected_material: ExpectedProvisioningVerifierMaterial
    expected_source: ExpectedProvisioningAuthoritySource
    expected_scope: ExpectedProvisioningAuthorityScope
    signature_text: str
    action: ProvisioningActionFacts
    lineage: PolicyLineageFacts
    facts: _CorrelatedFacts


def _exact_dataclass(left, right):
    if type(left) is not type(right):
        return False
    return all(
        type(getattr(left, item.name)) is type(getattr(right, item.name))
        and getattr(left, item.name) == getattr(right, item.name)
        for item in fields(left)
    )


def _authenticity_arguments(arguments):
    return {
        name: arguments[name]
        for name in (
            "confirmation_handle",
            "material_handle",
            "authority_handle",
            "designation_handle",
            "lease",
            "session",
            "pin_facts",
            "fresh_action",
            "fresh_lineage",
            "expected_payload",
            "expected_material",
            "expected_source",
            "expected_scope",
            "signature_text",
        )
    }


def _observation_arguments(arguments):
    return {
        "lineage_handle": arguments["lineage_handle"],
        "confirmation_handle": arguments["confirmation_handle"],
        "expected_payload": arguments["expected_payload"],
        "action": arguments["fresh_action"],
        "lineage": arguments["fresh_lineage"],
    }


class _ConfirmationLineageCorrelations:
    """Provider-internal opaque correlation; no witness or permission API."""

    def __init__(self, *, authenticity, observations):
        if (
            type(authenticity) is not _OriginalConfirmationAuthenticity
            or type(observations) is not _FreshJournalLineageObservations
            or observations._lineage._confirmation is not authenticity._confirmation
        ):
            raise ConfirmationLineageCorrelationDenied()
        self._authenticity = authenticity
        self._observations = observations
        self._records = {}

    def _abandon_all(self, *, handle=None, **arguments):
        self._records.pop(handle, None)
        observation_handle = arguments.get("observation_handle")
        lineage_handle = arguments.get("lineage_handle")
        confirmation_handle = arguments.get("confirmation_handle")
        self._observations._observations.pop(observation_handle, None)
        self._observations._lineage._abandon(lineage_handle)
        self._authenticity._records.pop(arguments.get("authenticity_handle"), None)
        try:
            confirmation = self._authenticity._confirmation._records.get(confirmation_handle)
            if confirmation is not None:
                self._authenticity._confirmation._abandon(confirmation_handle, confirmation)
        finally:
            self._authenticity._material._abandon_chain(
                arguments.get("material_handle"),
                arguments.get("authority_handle"),
                arguments.get("designation_handle"),
            )

    def _correlate(self, **arguments):
        authenticity_handle = arguments.get("authenticity_handle")
        observation_handle = arguments.get("observation_handle")
        lineage_handle = arguments.get("lineage_handle")
        confirmation_handle = arguments.get("confirmation_handle")
        if any(
            type(value) is not _Handle
            for value in (
                authenticity_handle,
                observation_handle,
                lineage_handle,
                confirmation_handle,
                arguments.get("material_handle"),
                arguments.get("authority_handle"),
                arguments.get("designation_handle"),
            )
        ):
            raise ConfirmationLineageCorrelationDenied()

        # Authenticity first, then the independently held live source and fresh
        # journal observation.  Both are repeated after exact comparison below.
        self._authenticity._require_open(authenticity_handle, **_authenticity_arguments(arguments))
        self._observations._require_fresh(observation_handle, **_observation_arguments(arguments))

        auth_record = self._authenticity._records[authenticity_handle]
        verified = auth_record.verified
        observation = self._observations._observations[observation_handle]
        lineage_record = self._observations._lineage._records[lineage_handle]
        confirmation_record = self._authenticity._confirmation._records[confirmation_handle]
        material_record = self._authenticity._material._records[arguments["material_handle"]]
        authority_record = self._authenticity._material._authority._records[
            arguments["authority_handle"]
        ]
        lease_record = self._authenticity._confirmation._serialization._lookup(arguments["lease"])

        payload = arguments.get("expected_payload")
        material = arguments.get("expected_material")
        source = arguments.get("expected_source")
        scope = arguments.get("expected_scope")
        action = arguments.get("fresh_action")
        lineage = arguments.get("fresh_lineage")
        pin = arguments.get("pin_facts")
        session = arguments.get("session")
        if (
            type(payload) is not ExpectedConfirmationPayload
            or type(material) is not ExpectedProvisioningVerifierMaterial
            or type(source) is not ExpectedProvisioningAuthoritySource
            or type(scope) is not ExpectedProvisioningAuthorityScope
            or type(action) is not ProvisioningActionFacts
            or type(lineage) is not PolicyLineageFacts
            or confirmation_record.lease is not arguments.get("lease")
            or confirmation_record.session is not session
            or confirmation_record.pin_facts is not pin
            or lease_record.session is not session
            or observation.journal_session is not self._observations._journal.session
            or observation.lineage_handle is not lineage_handle
            or observation.confirmation_handle is not confirmation_handle
            or lineage_record.confirmation_handle is not confirmation_handle
            or auth_record.confirmation_handle is not confirmation_handle
        ):
            raise ConfirmationLineageCorrelationDenied()

        action.__post_init__()
        lineage.__post_init__()
        payload.__post_init__()
        material.__post_init__()
        source.__post_init__()
        scope.__post_init__()
        pin.binding.__post_init__()
        head = observation.snapshot.head
        if type(observation.snapshot) is not _JournalSnapshot:
            raise ConfirmationLineageCorrelationDenied()
        lineage_key = _lineage_key(lineage)
        authenticity_lineage_digest = digest(
            rfc8785.dumps(
                [
                    lineage_key[0],
                    lineage_key[1],
                    lineage_key[2],
                    list(lineage_key[3]),
                    list(lineage_key[4]),
                ]
            )
        )
        live_lineage_digest = lineage_comparison_digest(lineage)
        head_action_digest = action_comparison_digest(action)
        receipt = authority_record.receipt
        material_verified = material_record.verified
        expected = _CorrelatedFacts(
            payload.confirmation_id,
            payload.action_id,
            payload.policy_digest,
            payload.designation_digest,
            payload.initializer_ref,
            payload.replay_id,
            payload.installation_id,
            scope.producer_ref,
            lineage.anchor_id,
            lineage.source_id,
            authenticity_lineage_digest,
            live_lineage_digest,
            lineage_record.record_digest,
            head_action_digest,
            action.predecessor_digest,
            action.policy.revision,
            head.journal_id,
            head.revision,
            head.trust_revision,
            head.head_digest,
            material_verified.verifier_key_id,
            material_verified.verifier_fingerprint,
            source.source_id,
            source.source_revision,
            receipt.semantic_revision,
            receipt.head_event_digest,
            material.material_id,
            material.material_revision,
            verified.payload_digest,
            verified.signature_digest,
        )
        if (
            verified.confirmation_id != payload.confirmation_id
            or verified.action_id != action.action_id
            or verified.policy_digest != action.confirmation.policy_digest
            or verified.designation_digest != pin.binding.designation_record_digest
            or verified.initializer_ref != action.confirmation.initializer_ref
            or verified.lineage_anchor_id != lineage.anchor_id
            or verified.lineage_source_id != lineage.source_id
            or verified.lineage_digest != authenticity_lineage_digest
            or verified.installation_id != lineage.installation_id
            or verified.producer_ref != scope.producer_ref
            or verified.verifier_key_id != material_verified.verifier_key_id
            or verified.verifier_fingerprint != material_verified.verifier_fingerprint
            or verified.authority_revision != receipt.semantic_revision
            or verified.authority_head_digest != receipt.head_event_digest
            or verified.material_id != material.material_id
            or verified.material_revision != material.material_revision
            or payload.confirmation_id != action.confirmation.provenance_id
            or payload.action_id != action.action_id
            or payload.installation_id != lineage.installation_id
            or payload.initializer_ref != scope.producer_ref
            or payload.designation_digest != pin.binding.designation_record_digest
            or action != lineage.actions[-1]
            or lineage.statuses[-1] != "ACTIVE"
            or head != pin.binding.journal
            or head != pin.binding.installed_pin
            or observation.snapshot.history == ()
            or source.head_event_digest != receipt.head_event_digest
        ):
            raise ConfirmationLineageCorrelationDenied()

        self._authenticity._require_open(authenticity_handle, **_authenticity_arguments(arguments))
        self._observations._require_fresh(observation_handle, **_observation_arguments(arguments))
        if (
            self._authenticity._confirmation._serialization._lookup(arguments["lease"])
            is not lease_record
            or observation.journal_transaction
            is not self._observations._root_transaction(observation.journal_session)
        ):
            raise ConfirmationLineageCorrelationDenied()
        return expected, lease_record.transaction, observation.journal_transaction

    @contextmanager
    def _open_correlation(self, **arguments):
        handle = None
        try:
            facts, caller_transaction, journal_transaction = self._correlate(**arguments)
            handle = _Handle(_MINT)
            self._records[handle] = _Record(
                arguments["authenticity_handle"],
                arguments["observation_handle"],
                arguments["confirmation_handle"],
                arguments["lineage_handle"],
                arguments["material_handle"],
                arguments["authority_handle"],
                arguments["designation_handle"],
                arguments["lease"],
                arguments["session"],
                caller_transaction,
                journal_transaction,
                arguments["pin_facts"],
                arguments["expected_payload"],
                arguments["expected_material"],
                arguments["expected_source"],
                arguments["expected_scope"],
                arguments["signature_text"],
                arguments["fresh_action"],
                arguments["fresh_lineage"],
                facts,
            )
            try:
                yield handle
            finally:
                self._records.pop(handle, None)
        except Exception:
            self._abandon_all(handle=handle, **arguments)
            raise ConfirmationLineageCorrelationDenied() from None

    def _require_open(self, handle, **arguments):
        if type(handle) is not _Handle or handle not in self._records:
            raise ConfirmationLineageCorrelationDenied()
        record = self._records[handle]
        stored = {
            "authenticity_handle": record.authenticity_handle,
            "observation_handle": record.observation_handle,
            "confirmation_handle": record.confirmation_handle,
            "lineage_handle": record.lineage_handle,
            "material_handle": record.material_handle,
            "authority_handle": record.authority_handle,
            "designation_handle": record.designation_handle,
        }
        try:
            if (
                any(arguments.get(name) is not value for name, value in stored.items())
                or arguments.get("lease") is not record.lease
                or arguments.get("session") is not record.session
                or arguments.get("pin_facts") is not record.pin_facts
                or not _exact_dataclass(record.expected_payload, arguments.get("expected_payload"))
                or not _exact_dataclass(
                    record.expected_material, arguments.get("expected_material")
                )
                or not _exact_dataclass(record.expected_source, arguments.get("expected_source"))
                or not _exact_dataclass(record.expected_scope, arguments.get("expected_scope"))
                or type(arguments.get("signature_text")) is not str
                or arguments.get("signature_text") != record.signature_text
            ):
                raise ConfirmationLineageCorrelationDenied()
            facts, caller_transaction, journal_transaction = self._correlate(**arguments)
            if (
                not _exact_dataclass(record.facts, facts)
                or caller_transaction is not record.caller_transaction
                or journal_transaction is not record.journal_transaction
            ):
                raise ConfirmationLineageCorrelationDenied()
        except Exception:
            self._abandon_all(handle=handle, **stored)
            raise ConfirmationLineageCorrelationDenied() from None


__all__ = ["ConfirmationLineageCorrelationDenied"]
