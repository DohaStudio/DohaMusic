"""Held live policy-lineage record mechanics, not admission or store provisioning."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass

import rfc8785

from backend.bootstrap_authority.confirmation_payload import ExpectedConfirmationPayload
from backend.bootstrap_authority.confirmation_snapshot import _OriginalConfirmationSnapshots
from backend.bootstrap_authority.contracts import require_digest, require_revision, require_uuid
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.provisioning_binding import (
    ProvisioningBindingDenied,
    action_comparison_digest,
    lineage_comparison_digest,
    require_current_lineage_matches,
)
from backend.bootstrap_authority.source_custody import (
    SourceCustodyPolicy,
    _CustodyDesignationRecordFiles,
)
from backend.bootstrap_authority.witness_lifetime import _MINT, _Handle

LINEAGE_RECORD_FILE = "policy-lineage-current-v1.json"
LINEAGE_SCHEMA = "dohamusic/policy-lineage-current/v1"
FIELDS = frozenset(
    {
        "schema",
        "journal_id",
        "journal_revision",
        "journal_trust_revision",
        "journal_head_digest",
        "installation_id",
        "anchor_id",
        "source_id",
        "lineage_digest",
        "head_action_digest",
        "confirmation_id",
        "original_confirmation_digest",
        "initializer_ref",
        "policy_digest",
        "designation_digest",
        "semantic_revision",
        "predecessor_digest",
        "status",
    }
)


class _LineageFiles(_CustodyDesignationRecordFiles):
    _fixed_name = LINEAGE_RECORD_FILE


def _reject_number(value):
    raise ValueError("NON_INTEGER_NUMBER")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE")
        result[key] = value
    return result


def _expected(lineage, action, pin):
    require_current_lineage_matches(observed=lineage, expected=lineage)
    action_comparison_digest(action)
    if lineage.actions[-1] is not action and lineage.actions[-1] != action:
        raise ProvisioningBindingDenied()
    binding = pin.binding
    binding.__post_init__()
    head = binding.journal
    return {
        "schema": LINEAGE_SCHEMA,
        "journal_id": head.journal_id,
        "journal_revision": head.revision,
        "journal_trust_revision": head.trust_revision,
        "journal_head_digest": head.head_digest,
        "installation_id": lineage.installation_id,
        "anchor_id": lineage.anchor_id,
        "source_id": lineage.source_id,
        "lineage_digest": lineage_comparison_digest(lineage),
        "head_action_digest": action_comparison_digest(action),
        "confirmation_id": action.confirmation.provenance_id,
        "original_confirmation_digest": action.confirmation.original_confirmation_digest,
        "initializer_ref": action.confirmation.initializer_ref,
        "policy_digest": action.confirmation.policy_digest,
        "designation_digest": binding.designation_record_digest,
        "semantic_revision": action.policy.revision,
        "predecessor_digest": action.predecessor_digest,
        "status": "ACTIVE",
    }


def parse_live_lineage_record(raw, *, lineage, action, pin):
    """Exact canonical current-record comparison; no source provenance or witness mint."""
    try:
        expected = _expected(lineage, action, pin)
        if type(raw) is not bytes or not 0 < len(raw) <= 1_048_576:
            raise ValueError("SIZE")
        record = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if type(record) is not dict or set(record) != FIELDS:
            raise ValueError("FIELDS")
        for key in (
            "schema",
            "journal_id",
            "journal_head_digest",
            "installation_id",
            "anchor_id",
            "source_id",
            "lineage_digest",
            "head_action_digest",
            "confirmation_id",
            "original_confirmation_digest",
            "initializer_ref",
            "policy_digest",
            "designation_digest",
            "status",
        ):
            if type(record[key]) is not str:
                raise ValueError("TYPE")
        for key in ("journal_revision", "journal_trust_revision", "semantic_revision"):
            require_revision(record[key])
        for key in ("journal_id", "installation_id", "anchor_id", "source_id", "confirmation_id"):
            require_uuid(record[key])
        for key in (
            "journal_head_digest",
            "lineage_digest",
            "head_action_digest",
            "original_confirmation_digest",
            "policy_digest",
            "designation_digest",
        ):
            require_digest(record[key])
        predecessor = record["predecessor_digest"]
        if predecessor is not None:
            require_digest(predecessor)
        if record != expected or rfc8785.dumps(record) != raw:
            raise ValueError("MISMATCH")
        return digest(raw)
    except Exception:
        raise PrivateFactsDenied() from None


@dataclass(slots=True, repr=False)
class _Record:
    confirmation_handle: _Handle
    record_digest: str


class _LivePolicyLineageSnapshots:
    """Separate held current record; production source/provisioning remains unavailable."""

    def __init__(self, *, trusted_root, confirmation_snapshots, lineage_policy):
        if (
            type(confirmation_snapshots) is not _OriginalConfirmationSnapshots
            or type(lineage_policy) is not SourceCustodyPolicy
        ):
            raise PrivateFactsDenied()
        self._confirmation = confirmation_snapshots
        self._files = _LineageFiles(trusted_root, lineage_policy)
        confirmation_files = confirmation_snapshots._files
        designation_files = confirmation_snapshots._designation._files
        if not self._files._paths == confirmation_files._paths == designation_files._paths:
            raise PrivateFactsDenied()
        policy = confirmation_files._policy
        if (
            lineage_policy.root_identity != policy.root_identity
            or lineage_policy.record_identity
            in {policy.record_identity, designation_files._policy.record_identity}
            or lineage_policy.owner_sid != policy.owner_sid
            or lineage_policy.allowed_sids != policy.allowed_sids
            or lineage_policy.dacl != policy.dacl
        ):
            raise PrivateFactsDenied()
        self._records = {}

    def _abandon(self, handle):
        self._records.pop(handle, None)

    @contextmanager
    def _open_current(self, *, confirmation_handle, expected_payload, action, lineage):
        if type(expected_payload) is not ExpectedConfirmationPayload:
            raise PrivateFactsDenied()
        try:
            self._confirmation._require_canonical_payload(
                confirmation_handle,
                expected=expected_payload,
                fresh_action=action,
                fresh_lineage=lineage,
            )
            parent = self._confirmation._records[confirmation_handle]
            with self._files._snapshot() as raw:
                record_digest = parse_live_lineage_record(
                    raw, lineage=lineage, action=action, pin=parent.pin_facts
                )
                self._confirmation._require_canonical_payload(
                    confirmation_handle,
                    expected=expected_payload,
                    fresh_action=action,
                    fresh_lineage=lineage,
                )
                self._files._require_same_bytes(record_digest)
                handle = _Handle(_MINT)
                self._records[handle] = _Record(confirmation_handle, record_digest)
                try:
                    yield handle
                finally:
                    self._abandon(handle)
        except Exception:
            if confirmation_handle in self._confirmation._records:
                parent = self._confirmation._records[confirmation_handle]
                self._confirmation._abandon(confirmation_handle, parent)
            raise PrivateFactsDenied() from None

    def _require_current(self, handle, *, confirmation_handle, expected_payload, action, lineage):
        if type(handle) is not _Handle or handle not in self._records:
            raise PrivateFactsDenied()
        record = self._records[handle]
        try:
            if record.confirmation_handle is not confirmation_handle:
                raise PrivateFactsDenied()
            self._confirmation._require_canonical_payload(
                confirmation_handle,
                expected=expected_payload,
                fresh_action=action,
                fresh_lineage=lineage,
            )
            parent = self._confirmation._records[confirmation_handle]
            raw = self._files._require_same_bytes(record.record_digest)
            if (
                parse_live_lineage_record(raw, lineage=lineage, action=action, pin=parent.pin_facts)
                != record.record_digest
            ):
                raise PrivateFactsDenied()
        except Exception:
            self._abandon(handle)
            if confirmation_handle in self._confirmation._records:
                parent = self._confirmation._records[confirmation_handle]
                self._confirmation._abandon(confirmation_handle, parent)
            raise PrivateFactsDenied() from None
