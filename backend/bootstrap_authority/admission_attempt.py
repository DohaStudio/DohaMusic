"""Provider-owned durable-admission candidate preparation; never admission.

This foundation binds one already-live CurrentnessWitness to one strictly
verified canonical lifecycle candidate.  It performs no journal write, flush,
commit, rollback or retry.  Only a future external journal transaction owner
may consume the opaque attempt and establish durable admission.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass, fields
from threading import RLock
from types import MappingProxyType
from uuid import uuid4

import rfc8785

from backend.bootstrap_authority.currentness_witness_handoff import (
    _CurrentnessWitnessHandoff,
    _WitnessRecord,
)
from backend.bootstrap_authority.lifecycle_verifier import (
    LifecycleExpectations,
    LifecycleIntegrityReceipt,
    digest,
    verify_lifecycle_integrity,
)
from backend.bootstrap_authority.witness_lifetime import _Handle


class AdmissionAttemptDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("ADMISSION_ATTEMPT_DENIED")


_ATTEMPT_MINT = object()


class _AdmissionAttempt:
    """Opaque provider-registry identity, distinct from CurrentnessWitness."""

    __slots__ = ()

    def __new__(cls, mint=None):
        if mint is not _ATTEMPT_MINT:
            raise AdmissionAttemptDenied()
        return super().__new__(cls)

    def __init_subclass__(cls, **kwargs):
        raise TypeError("OPAQUE_ADMISSION_ATTEMPT")

    def __copy__(self):
        raise TypeError("OPAQUE_ADMISSION_ATTEMPT")

    def __deepcopy__(self, memo):
        raise TypeError("OPAQUE_ADMISSION_ATTEMPT")

    def __reduce_ex__(self, protocol):
        raise TypeError("OPAQUE_ADMISSION_ATTEMPT")

    def __repr__(self):
        return "<opaque admission attempt>"


@dataclass(frozen=True, slots=True, repr=False)
class _Candidate:
    canonical_event: bytes
    canonical_manifest: bytes
    event_id: str
    event_kind: str
    event_revision: int
    semantic_revision: int
    event_digest: str
    journal_id: str
    designation_id: str
    designation_record_digest: str
    deployment_owner_ref: str
    expected_head_digest: str
    expected_head_revision: int
    expected_semantic_revision: int
    affected_scopes: tuple[tuple[str, str, str], ...]
    expected: LifecycleExpectations


@dataclass(frozen=True, slots=True, repr=False)
class _AttemptRecord:
    handle: _AdmissionAttempt
    currentness_witness: _Handle
    currentness_record: _WitnessRecord
    currentness_arguments: Mapping[str, object]
    candidate: _Candidate
    correlation_digest: str
    attempt_id: str
    lease: object
    caller_transaction: object
    journal_session: object
    journal_transaction: object


def _correlation_digest(record: _WitnessRecord) -> str:
    facts = record.correlation_record.facts
    values = [getattr(facts, item.name) for item in fields(facts)]
    return digest(rfc8785.dumps(values))


def _canonical_candidate(
    artifact: object,
    manifest: object,
    *,
    expected: object,
    witness_record: _WitnessRecord,
) -> _Candidate:
    if (
        type(artifact) is not bytes
        or type(manifest) is not bytes
        or type(expected) is not LifecycleExpectations
    ):
        raise AdmissionAttemptDenied()
    binding = witness_record.binding
    binding.__post_init__()
    if type(expected.revision) is not int or type(expected.previous_trust_revision) is not int:
        raise AdmissionAttemptDenied()
    receipt = verify_lifecycle_integrity(artifact, manifest, expected=expected)
    if type(receipt) is not LifecycleIntegrityReceipt:
        raise AdmissionAttemptDenied()
    envelope = json.loads(receipt.canonical_envelope)
    payload = envelope["payload"]
    scopes = json.loads(manifest)
    canonical_manifest = rfc8785.dumps(scopes)
    head = binding.journal
    if (
        expected.journal_id != head.journal_id
        or expected.deployment_owner_ref != binding.deployment_owner_ref
        or expected.revision != head.revision + 1
        or expected.previous_trust_revision != head.trust_revision
        or expected.previous_event_digest != head.head_digest
        or expected.authoritative_scopes != binding.affected_scopes
        or payload["event_kind"] == "GENESIS"
        or payload["old_key_id"] != binding.root_key_id
        or payload["old_key_fingerprint"] != binding.root_fingerprint
        or payload["revision"] != expected.revision
        or payload["trust_revision"] != expected.revision
        or payload["previous_trust_revision"] != expected.previous_trust_revision
        or canonical_manifest != manifest
        or payload["designation_record_digest"] == binding.designation_record_digest
        or (
            payload["event_kind"] == "EXTERNAL_REDESIGNATION"
            and payload["designation_id"] == binding.designation_id
        )
        or (
            payload["event_kind"] != "EXTERNAL_REDESIGNATION"
            and payload["designation_id"] != binding.designation_id
        )
    ):
        raise AdmissionAttemptDenied()
    required_keys = {payload["old_key_id"]}
    if payload["new_key_id"] is not None:
        required_keys.add(payload["new_key_id"])
    if (
        type(expected.public_keys) is not tuple
        or len(expected.public_keys) != len(required_keys)
        or {item[0] for item in expected.public_keys} != required_keys
        or dict(expected.public_keys).get(binding.root_key_id) != binding.root_public_key
    ):
        raise AdmissionAttemptDenied()
    return _Candidate(
        receipt.canonical_envelope,
        canonical_manifest,
        payload["event_id"],
        payload["event_kind"],
        payload["revision"],
        payload["trust_revision"],
        receipt.event_digest,
        payload["journal_id"],
        payload["designation_id"],
        payload["designation_record_digest"],
        payload["deployment_owner_ref"],
        payload["previous_event_digest"],
        payload["revision"] - 1,
        payload["previous_trust_revision"],
        expected.authoritative_scopes,
        expected,
    )


class _AdmissionAttemptProvider:
    """Internal preparation authority for one exact candidate and witness.

    Registry membership, not caller-visible fields, establishes an attempt.
    The provider deliberately has no append/commit/admit/reconcile API.
    """

    def __init__(self, *, currentness_handoff):
        if type(currentness_handoff) is not _CurrentnessWitnessHandoff:
            raise AdmissionAttemptDenied()
        self._currentness = currentness_handoff
        self._lock = RLock()
        self._records: dict[_AdmissionAttempt, _AttemptRecord] = {}
        self._by_witness: dict[_Handle, _AdmissionAttempt] = {}

    def _invalidate(self, record: _AttemptRecord | None) -> None:
        if record is None:
            return
        with self._lock:
            self._records.pop(record.handle, None)
            if self._by_witness.get(record.currentness_witness) is record.handle:
                self._by_witness.pop(record.currentness_witness, None)
        self._currentness._invalidate(record.currentness_record)

    def _require_witness(self, witness, *, arguments):
        if type(witness) is not _Handle:
            raise AdmissionAttemptDenied()
        record = self._currentness._records.get(witness)
        if type(record) is not _WitnessRecord or record.witness is not witness:
            raise AdmissionAttemptDenied()
        try:
            self._currentness._require_current(witness, **arguments)
            if self._currentness._records.get(witness) is not record:
                raise AdmissionAttemptDenied()
            return record
        except Exception:
            self._currentness._invalidate(record)
            raise AdmissionAttemptDenied() from None

    @contextmanager
    def _open_attempt(
        self,
        *,
        currentness_witness,
        artifact,
        manifest,
        expected,
        **currentness_arguments,
    ):
        record = None
        witness_record = None
        handle = None
        existing_winner = False
        try:
            with self._lock:
                witness_record = self._require_witness(
                    currentness_witness,
                    arguments=currentness_arguments,
                )
                if currentness_witness in self._by_witness:
                    existing_winner = True
                    raise AdmissionAttemptDenied()
                candidate = _canonical_candidate(
                    artifact,
                    manifest,
                    expected=expected,
                    witness_record=witness_record,
                )
                self._currentness._require_current(
                    currentness_witness,
                    **currentness_arguments,
                )
                if self._currentness._records.get(currentness_witness) is not witness_record:
                    raise AdmissionAttemptDenied()
                handle = _AdmissionAttempt(_ATTEMPT_MINT)
                record = _AttemptRecord(
                    handle,
                    currentness_witness,
                    witness_record,
                    MappingProxyType(dict(currentness_arguments)),
                    candidate,
                    _correlation_digest(witness_record),
                    str(uuid4()),
                    witness_record.lease,
                    witness_record.transaction,
                    witness_record.correlation_record.journal_transaction.session,
                    witness_record.correlation_record.journal_transaction,
                )
                self._records[handle] = record
                self._by_witness[currentness_witness] = handle
            try:
                yield handle
            finally:
                self._invalidate(record)
        except AdmissionAttemptDenied:
            if record is None and witness_record is not None and not existing_winner:
                self._currentness._invalidate(witness_record)
            raise
        except Exception:
            if record is not None:
                with suppress(Exception):
                    self._invalidate(record)
            elif witness_record is not None:
                with suppress(Exception):
                    self._currentness._invalidate(witness_record)
            raise AdmissionAttemptDenied() from None

    def _require_prepared(self, admission_attempt, *, currentness_witness, **currentness_arguments):
        if type(admission_attempt) is not _AdmissionAttempt:
            raise AdmissionAttemptDenied()
        with self._lock:
            record = self._records.get(admission_attempt)
            if type(record) is not _AttemptRecord or record.handle is not admission_attempt:
                raise AdmissionAttemptDenied()
            try:
                if (
                    currentness_witness is not record.currentness_witness
                    or self._by_witness.get(record.currentness_witness) is not admission_attempt
                    or any(
                        currentness_arguments.get(name) is not value
                        for name, value in record.currentness_arguments.items()
                        if name
                        in {
                            "attempt",
                            "correlation_handle",
                            "lease",
                            "session",
                            "pin_facts",
                        }
                    )
                    or currentness_arguments.keys() != record.currentness_arguments.keys()
                ):
                    raise AdmissionAttemptDenied()
                self._currentness._require_current(
                    record.currentness_witness,
                    **currentness_arguments,
                )
                if (
                    self._currentness._records.get(record.currentness_witness)
                    is not record.currentness_record
                    or record.currentness_record.lease is not record.lease
                    or record.currentness_record.transaction is not record.caller_transaction
                    or _correlation_digest(record.currentness_record) != record.correlation_digest
                ):
                    raise AdmissionAttemptDenied()
                return record
            except Exception:
                self._invalidate(record)
                raise AdmissionAttemptDenied() from None


__all__ = ["AdmissionAttemptDenied"]
