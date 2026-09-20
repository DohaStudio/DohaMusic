"""Held ACTIVE provisioning-verifier material; never currentness or admission.

The fixed custody-bound material source is usable only while its parent ADR-094
authority source, designation/pin lease and caller transaction remain live.
Public verifier bytes are not secret, but existence or fingerprint equality alone
is not provisioning authority.  No production port or key installer is exposed.
"""

from __future__ import annotations

import base64
import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass, fields

import rfc8785

from backend.bootstrap_authority.contracts import (
    require_digest,
    require_reference,
    require_revision,
    require_uuid,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.provisioning_authority import (
    CONFIRMATION_SIGNING_DOMAIN,
    PURPOSE,
    ExpectedProvisioningAuthorityScope,
    ProvisioningAuthorityIntegrityReceipt,
)
from backend.bootstrap_authority.provisioning_authority_source import (
    ExpectedProvisioningAuthoritySource,
    _ProvisioningAuthoritySourceSnapshots,
)
from backend.bootstrap_authority.source_custody import (
    SourceCustodyPolicy,
    _CustodyDesignationRecordFiles,
)
from backend.bootstrap_authority.witness_lifetime import _MINT, _Handle

MATERIAL_FILE = "provisioning-verifier-material-v1.json"
MATERIAL_SCHEMA = "dohamusic/scoped-provisioning-verifier-material/v1"
MAX_MATERIAL_BYTES = 16_384
FIELDS = frozenset(
    {
        "schema",
        "algorithm",
        "material_id",
        "material_revision",
        "source_id",
        "authorization_id",
        "authority_revision",
        "authority_head_digest",
        "installation_id",
        "producer_ref",
        "purpose",
        "confirmation_signing_domain",
        "verifier_key_id",
        "verifier_fingerprint",
        "public_key",
    }
)


class ProvisioningVerifierMaterialDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PROVISIONING_VERIFIER_MATERIAL_DENIED")


@dataclass(frozen=True, slots=True)
class ExpectedProvisioningVerifierMaterial:
    material_id: str
    material_revision: int

    def __post_init__(self) -> None:
        if type(self.material_id) is not str:
            raise ValueError("MATERIAL_EXPECTATION")
        require_uuid(self.material_id)
        require_revision(self.material_revision)


@dataclass(frozen=True, slots=True, repr=False)
class _VerifiedMaterial:
    material_id: str
    material_revision: int
    verifier_key_id: str
    verifier_fingerprint: str
    public_key: bytes
    material_digest: str


@dataclass(slots=True, repr=False)
class _Record:
    authority_handle: _Handle
    designation_handle: _Handle
    expected_material: ExpectedProvisioningVerifierMaterial
    expected_source: ExpectedProvisioningAuthoritySource
    expected_scope: ExpectedProvisioningAuthorityScope
    verified: _VerifiedMaterial


class _VerifierMaterialFiles(_CustodyDesignationRecordFiles):
    _fixed_name = MATERIAL_FILE


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE")
        result[key] = value
    return result


def _reject_number(_):
    raise ValueError("NUMBER")


def _exact_dataclass(left, right):
    if type(left) is not type(right):
        return False
    return all(
        type(getattr(left, item.name)) is type(getattr(right, item.name))
        and getattr(left, item.name) == getattr(right, item.name)
        for item in fields(left)
    )


def _decode_material(
    raw,
    *,
    expected_material,
    expected_source,
    expected_scope,
    authority_receipt,
):
    if (
        type(expected_material) is not ExpectedProvisioningVerifierMaterial
        or type(expected_source) is not ExpectedProvisioningAuthoritySource
        or type(expected_scope) is not ExpectedProvisioningAuthorityScope
        or type(authority_receipt) is not ProvisioningAuthorityIntegrityReceipt
    ):
        raise ValueError("EXPECTATION")
    expected_material.__post_init__()
    expected_source.__post_init__()
    expected_scope.__post_init__()
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MATERIAL_BYTES:
        raise ValueError("SIZE")
    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_unique_object,
        parse_float=_reject_number,
        parse_constant=_reject_number,
    )
    if type(value) is not dict or set(value) != FIELDS or raw != rfc8785.dumps(value):
        raise ValueError("WIRE")
    exact = {
        "schema": MATERIAL_SCHEMA,
        "algorithm": "Ed25519",
        "material_id": expected_material.material_id,
        "material_revision": expected_material.material_revision,
        "source_id": expected_source.source_id,
        "authorization_id": expected_scope.authorization_id,
        "authority_revision": authority_receipt.semantic_revision,
        "authority_head_digest": authority_receipt.head_event_digest,
        "installation_id": expected_scope.installation_id,
        "producer_ref": expected_scope.producer_ref,
        "purpose": PURPOSE,
        "confirmation_signing_domain": CONFIRMATION_SIGNING_DOMAIN,
        "verifier_key_id": authority_receipt.current_verifier_key_id,
        "verifier_fingerprint": authority_receipt.current_verifier_fingerprint,
    }
    for name, expected in exact.items():
        if type(value[name]) is not type(expected) or value[name] != expected:
            raise ValueError("BINDING")
    for name, validator in (
        ("material_id", require_uuid),
        ("source_id", require_uuid),
        ("authorization_id", require_uuid),
        ("installation_id", require_uuid),
        ("authority_head_digest", require_digest),
        ("verifier_fingerprint", require_digest),
        ("producer_ref", require_reference),
        ("verifier_key_id", require_reference),
    ):
        validator(value[name])
    require_revision(value["material_revision"])
    require_revision(value["authority_revision"])
    text = value["public_key"]
    if type(text) is not str or len(text) != 43 or "=" in text:
        raise ValueError("PUBLIC_KEY")
    public_key = base64.b64decode(text + "=", altchars=b"-_", validate=True)
    if (
        len(public_key) != 32
        or base64.urlsafe_b64encode(public_key).rstrip(b"=").decode("ascii") != text
        or "sha256:" + hashlib.sha256(public_key).hexdigest()
        != authority_receipt.current_verifier_fingerprint
    ):
        raise ValueError("PUBLIC_KEY")
    return _VerifiedMaterial(
        expected_material.material_id,
        expected_material.material_revision,
        authority_receipt.current_verifier_key_id,
        authority_receipt.current_verifier_fingerprint,
        public_key,
        digest(raw),
    )


class _ProvisioningVerifierMaterialSnapshots:
    """Internal held material observation; no signer, witness, or admission API."""

    def __init__(self, *, trusted_root, authority_snapshots, material_policy):
        if (
            type(authority_snapshots) is not _ProvisioningAuthoritySourceSnapshots
            or type(material_policy) is not SourceCustodyPolicy
        ):
            raise ProvisioningVerifierMaterialDenied()
        self._authority = authority_snapshots
        self._files = _VerifierMaterialFiles(trusted_root, material_policy)
        parent = authority_snapshots._files
        designation = authority_snapshots._designation._files
        if (
            self._files._paths != parent._paths
            or material_policy.root_identity != parent._policy.root_identity
            or material_policy.record_identity
            in {parent._policy.record_identity, designation._policy.record_identity}
            or material_policy.owner_sid != parent._policy.owner_sid
            or material_policy.allowed_sids != parent._policy.allowed_sids
            or material_policy.dacl != parent._policy.dacl
        ):
            raise ProvisioningVerifierMaterialDenied()
        self._records = {}

    def _abandon_chain(self, handle, authority_handle, designation_handle):
        self._records.pop(handle, None)
        self._authority._abandon_chain(authority_handle, designation_handle)

    def _require_authority(
        self,
        authority_handle,
        *,
        designation_handle,
        lease,
        session,
        pin_facts,
        expected_source,
        expected_scope,
    ):
        self._authority._require_open(
            authority_handle,
            designation_handle=designation_handle,
            lease=lease,
            session=session,
            pin_facts=pin_facts,
            expected_source=expected_source,
            expected_scope=expected_scope,
        )
        return self._authority._records[authority_handle].receipt

    @contextmanager
    def _open_material(
        self,
        *,
        authority_handle,
        designation_handle,
        lease,
        session,
        pin_facts,
        expected_source,
        expected_scope,
        expected_material,
    ):
        handle = None
        try:
            receipt = self._require_authority(
                authority_handle,
                designation_handle=designation_handle,
                lease=lease,
                session=session,
                pin_facts=pin_facts,
                expected_source=expected_source,
                expected_scope=expected_scope,
            )
            with self._files._snapshot() as raw:
                verified = _decode_material(
                    raw,
                    expected_material=expected_material,
                    expected_source=expected_source,
                    expected_scope=expected_scope,
                    authority_receipt=receipt,
                )
                receipt = self._require_authority(
                    authority_handle,
                    designation_handle=designation_handle,
                    lease=lease,
                    session=session,
                    pin_facts=pin_facts,
                    expected_source=expected_source,
                    expected_scope=expected_scope,
                )
                reread = self._files._require_same_bytes(verified.material_digest)
                if not _exact_dataclass(
                    _decode_material(
                        reread,
                        expected_material=expected_material,
                        expected_source=expected_source,
                        expected_scope=expected_scope,
                        authority_receipt=receipt,
                    ),
                    verified,
                ):
                    raise ProvisioningVerifierMaterialDenied()
                handle = _Handle(_MINT)
                self._records[handle] = _Record(
                    authority_handle,
                    designation_handle,
                    expected_material,
                    expected_source,
                    expected_scope,
                    verified,
                )
                try:
                    yield handle
                finally:
                    self._records.pop(handle, None)
        except Exception:
            self._abandon_chain(handle, authority_handle, designation_handle)
            raise ProvisioningVerifierMaterialDenied() from None

    def _require_open(
        self,
        handle,
        *,
        authority_handle,
        designation_handle,
        lease,
        session,
        pin_facts,
        expected_source,
        expected_scope,
        expected_material,
    ):
        if type(handle) is not _Handle or handle not in self._records:
            raise ProvisioningVerifierMaterialDenied()
        record = self._records[handle]
        try:
            if (
                record.authority_handle is not authority_handle
                or record.designation_handle is not designation_handle
                or not _exact_dataclass(record.expected_material, expected_material)
                or not _exact_dataclass(record.expected_source, expected_source)
                or not _exact_dataclass(record.expected_scope, expected_scope)
            ):
                raise ProvisioningVerifierMaterialDenied()
            receipt = self._require_authority(
                authority_handle,
                designation_handle=designation_handle,
                lease=lease,
                session=session,
                pin_facts=pin_facts,
                expected_source=expected_source,
                expected_scope=expected_scope,
            )
            raw = self._files._require_same_bytes(record.verified.material_digest)
            verified = _decode_material(
                raw,
                expected_material=expected_material,
                expected_source=expected_source,
                expected_scope=expected_scope,
                authority_receipt=receipt,
            )
            if not _exact_dataclass(verified, record.verified):
                raise ProvisioningVerifierMaterialDenied()
            self._require_authority(
                authority_handle,
                designation_handle=designation_handle,
                lease=lease,
                session=session,
                pin_facts=pin_facts,
                expected_source=expected_source,
                expected_scope=expected_scope,
            )
        except Exception:
            self._abandon_chain(handle, authority_handle, designation_handle)
            raise ProvisioningVerifierMaterialDenied() from None


__all__ = ["ProvisioningVerifierMaterialDenied"]
