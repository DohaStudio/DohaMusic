"""Held Original Confirmation authenticity; never currentness or admission.

The detached signature is untrusted input.  Authenticity exists only while the
held canonical confirmation, ADR-095 ACTIVE verifier material, their parent
designation/pin lease and the caller transaction all remain live.  No signer,
credential issuer, production port, currentness witness or admission API exists.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import dataclass, fields

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.bootstrap_authority.confirmation_payload import ExpectedConfirmationPayload
from backend.bootstrap_authority.confirmation_snapshot import (
    _lineage_key,
    _OriginalConfirmationSnapshots,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.provisioning_authority import (
    CONFIRMATION_SIGNING_DOMAIN,
    ExpectedProvisioningAuthorityScope,
)
from backend.bootstrap_authority.provisioning_authority_source import (
    ExpectedProvisioningAuthoritySource,
)
from backend.bootstrap_authority.provisioning_verifier_material import (
    ExpectedProvisioningVerifierMaterial,
    _ProvisioningVerifierMaterialSnapshots,
)
from backend.bootstrap_authority.witness_lifetime import _MINT, _Handle

SIGNATURE_DOMAIN = CONFIRMATION_SIGNING_DOMAIN.encode("ascii") + b"\x00"
SIGNATURE_TEXT_BYTES = 86


class OriginalConfirmationAuthenticityDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("ORIGINAL_CONFIRMATION_AUTHENTICITY_DENIED")


@dataclass(frozen=True, slots=True, repr=False)
class _VerifiedAuthenticity:
    confirmation_id: str
    action_id: str
    policy_digest: str
    designation_digest: str
    initializer_ref: str
    replay_id: str
    lineage_anchor_id: str
    lineage_source_id: str
    lineage_digest: str
    installation_id: str
    producer_ref: str
    verifier_key_id: str
    verifier_fingerprint: str
    authority_revision: int
    authority_head_digest: str
    material_id: str
    material_revision: int
    payload_digest: str
    signature_digest: str


@dataclass(slots=True, repr=False)
class _Record:
    confirmation_handle: _Handle
    material_handle: _Handle
    authority_handle: _Handle
    designation_handle: _Handle
    lease: object
    session: object
    expected_payload: ExpectedConfirmationPayload
    expected_material: ExpectedProvisioningVerifierMaterial
    expected_source: ExpectedProvisioningAuthoritySource
    expected_scope: ExpectedProvisioningAuthorityScope
    signature_text: str
    verified: _VerifiedAuthenticity


def _exact_dataclass(left, right):
    if type(left) is not type(right):
        return False
    return all(
        type(getattr(left, item.name)) is type(getattr(right, item.name))
        and getattr(left, item.name) == getattr(right, item.name)
        for item in fields(left)
    )


def _decode_signature(value):
    if type(value) is not str or len(value) != SIGNATURE_TEXT_BYTES or "=" in value:
        raise ValueError("SIGNATURE")
    signature = base64.b64decode(value + "==", altchars=b"-_", validate=True)
    if (
        len(signature) != 64
        or base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii") != value
    ):
        raise ValueError("SIGNATURE")
    return signature


def _verify_signature(public_key, signature_text, raw):
    if type(public_key) is not bytes or len(public_key) != 32 or type(raw) is not bytes:
        raise ValueError("SIGNATURE_INPUT")
    signature = _decode_signature(signature_text)
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, SIGNATURE_DOMAIN + raw)
    return digest(signature)


class _OriginalConfirmationAuthenticity:
    """Internal held signature result; no bool/receipt/currentness authority."""

    def __init__(self, *, confirmation_snapshots, material_snapshots):
        if (
            type(confirmation_snapshots) is not _OriginalConfirmationSnapshots
            or type(material_snapshots) is not _ProvisioningVerifierMaterialSnapshots
            or confirmation_snapshots._designation is not material_snapshots._authority._designation
            or confirmation_snapshots._files._paths != material_snapshots._files._paths
        ):
            raise OriginalConfirmationAuthenticityDenied()
        identities = {
            confirmation_snapshots._files._policy.record_identity,
            material_snapshots._files._policy.record_identity,
            material_snapshots._authority._files._policy.record_identity,
            confirmation_snapshots._designation._files._policy.record_identity,
        }
        if len(identities) != 4:
            raise OriginalConfirmationAuthenticityDenied()
        self._confirmation = confirmation_snapshots
        self._material = material_snapshots
        self._records = {}

    def _abandon_chain(
        self, handle, confirmation_handle, material_handle, authority_handle, designation_handle
    ):
        self._records.pop(handle, None)
        confirmation_record = self._confirmation._records.get(confirmation_handle)
        try:
            if confirmation_record is not None:
                self._confirmation._abandon(confirmation_handle, confirmation_record)
        finally:
            self._material._abandon_chain(material_handle, authority_handle, designation_handle)

    def _verify(
        self,
        *,
        confirmation_handle,
        material_handle,
        authority_handle,
        designation_handle,
        lease,
        session,
        pin_facts,
        fresh_action,
        fresh_lineage,
        expected_payload,
        expected_material,
        expected_source,
        expected_scope,
        signature_text,
    ):
        if (
            type(expected_payload) is not ExpectedConfirmationPayload
            or type(expected_material) is not ExpectedProvisioningVerifierMaterial
            or type(expected_source) is not ExpectedProvisioningAuthoritySource
            or type(expected_scope) is not ExpectedProvisioningAuthorityScope
        ):
            raise OriginalConfirmationAuthenticityDenied()
        boundary = self._confirmation._require_canonical_payload(
            confirmation_handle,
            expected=expected_payload,
            fresh_action=fresh_action,
            fresh_lineage=fresh_lineage,
        )
        self._material._require_open(
            material_handle,
            authority_handle=authority_handle,
            designation_handle=designation_handle,
            lease=lease,
            session=session,
            pin_facts=pin_facts,
            expected_source=expected_source,
            expected_scope=expected_scope,
            expected_material=expected_material,
        )
        material = self._material._records[material_handle].verified
        authority = self._material._authority._records[authority_handle].receipt
        if (
            expected_payload.installation_id != expected_scope.installation_id
            or expected_payload.initializer_ref != expected_scope.producer_ref
            or expected_payload.verifier_key_id != material.verifier_key_id
            or expected_payload.verifier_fingerprint != material.verifier_fingerprint
        ):
            raise OriginalConfirmationAuthenticityDenied()
        raw = self._confirmation._files._require_same_bytes(boundary.payload_digest)
        signature_digest = _verify_signature(material.public_key, signature_text, raw)
        self._material._require_open(
            material_handle,
            authority_handle=authority_handle,
            designation_handle=designation_handle,
            lease=lease,
            session=session,
            pin_facts=pin_facts,
            expected_source=expected_source,
            expected_scope=expected_scope,
            expected_material=expected_material,
        )
        repeated = self._confirmation._require_canonical_payload(
            confirmation_handle,
            expected=expected_payload,
            fresh_action=fresh_action,
            fresh_lineage=fresh_lineage,
        )
        if not _exact_dataclass(boundary, repeated):
            raise OriginalConfirmationAuthenticityDenied()
        lineage_key = _lineage_key(fresh_lineage)
        lineage_digest = digest(
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
        return _VerifiedAuthenticity(
            expected_payload.confirmation_id,
            expected_payload.action_id,
            expected_payload.policy_digest,
            expected_payload.designation_digest,
            expected_payload.initializer_ref,
            expected_payload.replay_id,
            lineage_key[0],
            lineage_key[2],
            lineage_digest,
            expected_payload.installation_id,
            expected_scope.producer_ref,
            material.verifier_key_id,
            material.verifier_fingerprint,
            authority.semantic_revision,
            authority.head_event_digest,
            material.material_id,
            material.material_revision,
            boundary.payload_digest,
            signature_digest,
        )

    @contextmanager
    def _open_authenticity(self, **arguments):
        handle = None
        try:
            verified = self._verify(**arguments)
            handle = _Handle(_MINT)
            self._records[handle] = _Record(
                arguments["confirmation_handle"],
                arguments["material_handle"],
                arguments["authority_handle"],
                arguments["designation_handle"],
                arguments["lease"],
                arguments["session"],
                arguments["expected_payload"],
                arguments["expected_material"],
                arguments["expected_source"],
                arguments["expected_scope"],
                arguments["signature_text"],
                verified,
            )
            try:
                yield handle
            finally:
                self._records.pop(handle, None)
        except Exception:
            self._abandon_chain(
                handle,
                arguments.get("confirmation_handle"),
                arguments.get("material_handle"),
                arguments.get("authority_handle"),
                arguments.get("designation_handle"),
            )
            raise OriginalConfirmationAuthenticityDenied() from None

    def _require_open(self, handle, **arguments):
        if type(handle) is not _Handle or handle not in self._records:
            raise OriginalConfirmationAuthenticityDenied()
        record = self._records[handle]
        try:
            if (
                record.confirmation_handle is not arguments.get("confirmation_handle")
                or record.material_handle is not arguments.get("material_handle")
                or record.authority_handle is not arguments.get("authority_handle")
                or record.designation_handle is not arguments.get("designation_handle")
                or record.lease is not arguments.get("lease")
                or record.session is not arguments.get("session")
                or not _exact_dataclass(record.expected_payload, arguments.get("expected_payload"))
                or not _exact_dataclass(
                    record.expected_material, arguments.get("expected_material")
                )
                or not _exact_dataclass(record.expected_source, arguments.get("expected_source"))
                or not _exact_dataclass(record.expected_scope, arguments.get("expected_scope"))
                or type(arguments.get("signature_text")) is not str
                or record.signature_text != arguments.get("signature_text")
            ):
                raise OriginalConfirmationAuthenticityDenied()
            verified = self._verify(**arguments)
            if not _exact_dataclass(record.verified, verified):
                raise OriginalConfirmationAuthenticityDenied()
        except Exception:
            self._abandon_chain(
                handle,
                record.confirmation_handle,
                record.material_handle,
                record.authority_handle,
                record.designation_handle,
            )
            raise OriginalConfirmationAuthenticityDenied() from None


__all__ = ["OriginalConfirmationAuthenticityDenied"]
