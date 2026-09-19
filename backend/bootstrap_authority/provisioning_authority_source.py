"""Held authenticated scoped-authority source; never currentness or admission.

The fixed private file is useful only while its custody-bound native handle, the
existing designation/pin lease and the caller transaction remain live.  Its
complete event history must independently pass ADR-093 verification.  The
provider-owned handle is not a CurrentnessWitness or authorization capability.
"""

from __future__ import annotations

import base64
import json
from contextlib import contextmanager
from dataclasses import dataclass

import rfc8785

from backend.bootstrap_authority.contracts import (
    PinnedRootVerifier,
    require_digest,
    require_revision,
    require_uuid,
)
from backend.bootstrap_authority.designation_snapshot import _DesignationRecordSnapshots
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.provisioning_authority import (
    MAX_EVENTS,
    ExpectedProvisioningAuthorityScope,
    ProvisioningAuthorityIntegrityReceipt,
    verify_provisioning_authority_history,
)
from backend.bootstrap_authority.source_custody import (
    SourceCustodyPolicy,
    _CustodyDesignationRecordFiles,
)
from backend.bootstrap_authority.witness_lifetime import _MINT, _Handle

SOURCE_FILE = "provisioning-authority-history-v1.json"
SOURCE_SCHEMA = "dohamusic/scoped-provisioning-authority-source/v1"
MAX_SOURCE_BYTES = 1_048_576
FIELDS = frozenset(
    {
        "schema",
        "source_id",
        "source_revision",
        "authorization_id",
        "root_key_id",
        "head_event_digest",
        "events",
    }
)


class ProvisioningAuthoritySourceDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PROVISIONING_AUTHORITY_SOURCE_DENIED")


@dataclass(frozen=True, slots=True)
class ExpectedProvisioningAuthoritySource:
    source_id: str
    source_revision: int
    head_event_digest: str

    def __post_init__(self) -> None:
        if type(self.source_id) is not str or type(self.head_event_digest) is not str:
            raise ValueError("SOURCE_EXPECTATION")
        require_uuid(self.source_id)
        require_revision(self.source_revision)
        require_digest(self.head_event_digest)


@dataclass(slots=True, repr=False)
class _Record:
    designation_handle: _Handle
    expected_source: ExpectedProvisioningAuthoritySource
    expected_scope: ExpectedProvisioningAuthorityScope
    source_digest: str
    receipt: ProvisioningAuthorityIntegrityReceipt


class _AuthoritySourceFiles(_CustodyDesignationRecordFiles):
    _fixed_name = SOURCE_FILE


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE")
        result[key] = value
    return result


def _reject_number(_):
    raise ValueError("NUMBER")


def _decode_source(raw, *, expected_source, expected_scope, root):
    if (
        type(expected_source) is not ExpectedProvisioningAuthoritySource
        or type(expected_scope) is not ExpectedProvisioningAuthorityScope
        or type(root) is not PinnedRootVerifier
    ):
        raise ValueError("EXPECTATION")
    expected_source.__post_init__()
    expected_scope.__post_init__()
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise ValueError("SIZE")
    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_unique_object,
        parse_float=_reject_number,
        parse_constant=_reject_number,
    )
    if type(value) is not dict or set(value) != FIELDS or raw != rfc8785.dumps(value):
        raise ValueError("WIRE")
    if (
        value["schema"] != SOURCE_SCHEMA
        or type(value["source_id"]) is not str
        or value["source_id"] != expected_source.source_id
        or type(value["source_revision"]) is not int
        or value["source_revision"] != expected_source.source_revision
        or type(value["authorization_id"]) is not str
        or value["authorization_id"] != expected_scope.authorization_id
        or type(value["root_key_id"]) is not str
        or value["root_key_id"] != root.root_key_id
        or type(value["head_event_digest"]) is not str
        or value["head_event_digest"] != expected_source.head_event_digest
        or type(value["events"]) is not list
        or not 0 < len(value["events"]) <= MAX_EVENTS
    ):
        raise ValueError("SCOPE")
    artifacts = []
    for text in value["events"]:
        if type(text) is not str or not text or "=" in text:
            raise ValueError("EVENT")
        artifact = base64.b64decode(text + "=" * (-len(text) % 4), altchars=b"-_", validate=True)
        if base64.urlsafe_b64encode(artifact).rstrip(b"=").decode("ascii") != text:
            raise ValueError("EVENT")
        artifacts.append(artifact)
    receipt = verify_provisioning_authority_history(
        tuple(artifacts), root=root, expected=expected_scope
    )
    if (
        receipt.lifecycle_state != "ACTIVE"
        or receipt.head_event_digest != expected_source.head_event_digest
        or receipt.semantic_revision != expected_source.source_revision
        or receipt.current_verifier_key_id is None
        or receipt.current_verifier_fingerprint is None
    ):
        raise ValueError("CURRENT_AUTHORITY")
    return receipt


class _ProvisioningAuthoritySourceSnapshots:
    """Internal held source observation; production composition remains absent."""

    def __init__(self, *, trusted_root, designation_snapshots, source_policy):
        if (
            type(designation_snapshots) is not _DesignationRecordSnapshots
            or type(designation_snapshots._files) is not _CustodyDesignationRecordFiles
            or type(source_policy) is not SourceCustodyPolicy
        ):
            raise ProvisioningAuthoritySourceDenied()
        self._designation = designation_snapshots
        self._files = _AuthoritySourceFiles(trusted_root, source_policy)
        parent = designation_snapshots._files
        if (
            self._files._paths != parent._paths
            or source_policy.root_identity != parent._policy.root_identity
            or source_policy.record_identity == parent._policy.record_identity
            or source_policy.owner_sid != parent._policy.owner_sid
            or source_policy.allowed_sids != parent._policy.allowed_sids
            or source_policy.dacl != parent._policy.dacl
        ):
            raise ProvisioningAuthoritySourceDenied()
        self._records = {}

    @staticmethod
    def _root(binding):
        return PinnedRootVerifier(
            root_key_id=binding.root_key_id,
            designation_id=binding.designation_id,
            deployment_owner_ref=binding.deployment_owner_ref,
            designation_digest=binding.designation_record_digest,
            public_key_fingerprint=binding.root_fingerprint,
            public_key=binding.root_public_key,
        )

    def _abandon_chain(self, handle, designation_handle):
        self._records.pop(handle, None)
        if designation_handle in self._designation._snapshots:
            parent = self._designation._snapshots[designation_handle]
            self._designation._abandon(designation_handle, parent)

    def _require_parent(self, designation_handle, *, lease, session, pin_facts):
        self._designation._require_open_snapshot(
            designation_handle, lease=lease, session=session, pin_facts=pin_facts
        )
        return self._root(pin_facts.binding)

    @contextmanager
    def _open_source(
        self,
        *,
        designation_handle,
        lease,
        session,
        pin_facts,
        expected_source,
        expected_scope,
    ):
        handle = None
        try:
            if (
                type(expected_source) is not ExpectedProvisioningAuthoritySource
                or type(expected_scope) is not ExpectedProvisioningAuthorityScope
            ):
                raise ProvisioningAuthoritySourceDenied()
            expected_source.__post_init__()
            expected_scope.__post_init__()
            root = self._require_parent(
                designation_handle, lease=lease, session=session, pin_facts=pin_facts
            )
            with self._files._snapshot() as raw:
                receipt = _decode_source(
                    raw,
                    expected_source=expected_source,
                    expected_scope=expected_scope,
                    root=root,
                )
                source_digest = digest(raw)
                root = self._require_parent(
                    designation_handle, lease=lease, session=session, pin_facts=pin_facts
                )
                reread = self._files._require_same_bytes(source_digest)
                if (
                    _decode_source(
                        reread,
                        expected_source=expected_source,
                        expected_scope=expected_scope,
                        root=root,
                    )
                    != receipt
                ):
                    raise ProvisioningAuthoritySourceDenied()
                handle = _Handle(_MINT)
                self._records[handle] = _Record(
                    designation_handle,
                    expected_source,
                    expected_scope,
                    source_digest,
                    receipt,
                )
                try:
                    yield handle
                finally:
                    self._records.pop(handle, None)
        except Exception:
            self._abandon_chain(handle, designation_handle)
            raise ProvisioningAuthoritySourceDenied() from None

    def _require_open(
        self,
        handle,
        *,
        designation_handle,
        lease,
        session,
        pin_facts,
        expected_source,
        expected_scope,
    ):
        if type(handle) is not _Handle or handle not in self._records:
            raise ProvisioningAuthoritySourceDenied()
        record = self._records[handle]
        try:
            if (
                record.designation_handle is not designation_handle
                or record.expected_source != expected_source
                or record.expected_scope != expected_scope
            ):
                raise ProvisioningAuthoritySourceDenied()
            root = self._require_parent(
                designation_handle, lease=lease, session=session, pin_facts=pin_facts
            )
            raw = self._files._require_same_bytes(record.source_digest)
            receipt = _decode_source(
                raw,
                expected_source=expected_source,
                expected_scope=expected_scope,
                root=root,
            )
            if receipt != record.receipt:
                raise ProvisioningAuthoritySourceDenied()
            self._require_parent(
                designation_handle, lease=lease, session=session, pin_facts=pin_facts
            )
        except Exception:
            self._abandon_chain(handle, designation_handle)
            raise ProvisioningAuthoritySourceDenied() from None


__all__ = ["ProvisioningAuthoritySourceDenied"]
