"""Scoped provisioning-authority event integrity; never currentness or admission.

ADR-093 authorizes the ADR-076 Product/Deployment root to issue one narrowly
scoped purpose.  This module verifies a complete, bounded, root-signed event
history.  It does not provision a root, authenticate a source, verify an
Original Confirmation, or mint a witness/capability.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass

import rfc8785
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.bootstrap_authority.contracts import (
    PinnedRootVerifier,
    require_digest,
    require_reference,
    require_revision,
    require_uuid,
)

SCHEMA = "dohamusic/scoped-provisioning-authority-event/v1"
SIGNATURE_DOMAIN = b"DohaMusicScopedProvisioningAuthorityEventV1\x00"
PURPOSE = "INSTALLATION_POLICY_PROVISIONING_ONLY"
CONFIRMATION_SIGNING_DOMAIN = "DohaMusicOriginalInitializerConfirmationV1"
LINEAGE_SIGNING_DOMAIN = "DohaMusicLivePolicyLineageProvisioningV1"
POLICY_DOMAIN = "dohamusic/installation-policy-provisioning/v1"
MAX_EVENT_BYTES = 16_384
MAX_EVENTS = 256
EVENT_FIELDS = frozenset(
    {
        "schema",
        "algorithm",
        "authorization_id",
        "event_id",
        "semantic_revision",
        "previous_event_digest",
        "event_kind",
        "root_key_id",
        "designation_id",
        "deployment_owner_ref",
        "designation_digest",
        "installation_id",
        "producer_ref",
        "purpose",
        "confirmation_signing_domain",
        "lineage_signing_domain",
        "policy_domain",
        "old_verifier_key_id",
        "old_verifier_fingerprint",
        "new_verifier_key_id",
        "new_verifier_fingerprint",
        "governance_provenance_digest",
    }
)


class ProvisioningAuthorityDenied(ValueError):
    """One safe denial for malformed, mismatched, stale, or unverifiable input."""

    def __init__(self) -> None:
        super().__init__("PROVISIONING_AUTHORITY_DENIED")


def _exact_text(value: object, validator) -> None:
    if type(value) is not str:
        raise ValueError("TEXT")
    validator(value)


@dataclass(frozen=True, slots=True)
class ExpectedProvisioningAuthorityScope:
    """Independent exact expectations; not a root/currentness/source witness."""

    authorization_id: str
    installation_id: str
    producer_ref: str
    governance_provenance_digest: str
    purpose: str = PURPOSE
    confirmation_signing_domain: str = CONFIRMATION_SIGNING_DOMAIN
    lineage_signing_domain: str = LINEAGE_SIGNING_DOMAIN
    policy_domain: str = POLICY_DOMAIN

    def __post_init__(self) -> None:
        _exact_text(self.authorization_id, require_uuid)
        _exact_text(self.installation_id, require_uuid)
        _exact_text(self.producer_ref, require_reference)
        _exact_text(self.governance_provenance_digest, require_digest)
        if (
            type(self.purpose) is not str
            or type(self.confirmation_signing_domain) is not str
            or type(self.lineage_signing_domain) is not str
            or type(self.policy_domain) is not str
            or self.purpose != PURPOSE
            or self.confirmation_signing_domain != CONFIRMATION_SIGNING_DOMAIN
            or self.lineage_signing_domain != LINEAGE_SIGNING_DOMAIN
            or self.policy_domain != POLICY_DOMAIN
        ):
            raise ValueError("DOMAIN")


@dataclass(frozen=True, slots=True)
class ProvisioningVerifierHistory:
    key_id: str
    fingerprint: str
    status: str
    invalidated_at_revision: int | None


@dataclass(frozen=True, slots=True, repr=False)
class ProvisioningAuthorityIntegrityReceipt:
    """Verified public history only; no capability/current-source assertion API."""

    authorization_id: str
    installation_id: str
    producer_ref: str
    purpose: str
    semantic_revision: int
    head_event_digest: str
    current_verifier_key_id: str | None
    current_verifier_fingerprint: str | None
    lifecycle_state: str
    verifier_history: tuple[ProvisioningVerifierHistory, ...]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE")
        result[key] = value
    return result


def _reject_number(_: str) -> None:
    raise ValueError("NUMBER")


def _decode_event(raw: bytes) -> tuple[dict[str, object], bytes, bytes, bytes]:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_EVENT_BYTES:
        raise ValueError("SIZE")
    envelope = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_unique_object,
        parse_float=_reject_number,
        parse_constant=_reject_number,
    )
    if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
        raise ValueError("ENVELOPE")
    payload = envelope["payload"]
    signature_text = envelope["signature"]
    if type(payload) is not dict or set(payload) != EVENT_FIELDS:
        raise ValueError("FIELDS")
    if type(signature_text) is not str or len(signature_text) != 86:
        raise ValueError("SIGNATURE")
    signature = base64.b64decode(signature_text + "==", altchars=b"-_", validate=True)
    if (
        len(signature) != 64
        or base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii") != signature_text
    ):
        raise ValueError("SIGNATURE")
    canonical_payload = rfc8785.dumps(payload)
    canonical_envelope = rfc8785.dumps(envelope)
    return payload, signature, canonical_payload, canonical_envelope


def _validate_root(root: PinnedRootVerifier) -> None:
    if type(root) is not PinnedRootVerifier:
        raise ValueError("ROOT")
    for value, validator in (
        (root.root_key_id, require_reference),
        (root.designation_id, require_uuid),
        (root.deployment_owner_ref, require_reference),
        (root.designation_digest, require_digest),
        (root.public_key_fingerprint, require_digest),
    ):
        _exact_text(value, validator)
    if type(root.public_key) is not bytes or len(root.public_key) != 32:
        raise ValueError("ROOT")
    if _digest(root.public_key) != root.public_key_fingerprint:
        raise ValueError("ROOT")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _validate_common(
    payload: dict[str, object],
    *,
    root: PinnedRootVerifier,
    expected: ExpectedProvisioningAuthorityScope,
) -> None:
    if payload["schema"] != SCHEMA or payload["algorithm"] != "Ed25519":
        raise ValueError("SCHEMA")
    for name in ("authorization_id", "event_id", "designation_id", "installation_id"):
        _exact_text(payload[name], require_uuid)
    for name in ("root_key_id", "deployment_owner_ref", "producer_ref"):
        _exact_text(payload[name], require_reference)
    for name in ("designation_digest", "governance_provenance_digest"):
        _exact_text(payload[name], require_digest)
    require_revision(payload["semantic_revision"])
    previous = payload["previous_event_digest"]
    if previous is not None:
        _exact_text(previous, require_digest)
    for name in (
        "old_verifier_key_id",
        "new_verifier_key_id",
    ):
        value = payload[name]
        if value is not None:
            _exact_text(value, require_reference)
    for name in (
        "old_verifier_fingerprint",
        "new_verifier_fingerprint",
    ):
        value = payload[name]
        if value is not None:
            _exact_text(value, require_digest)
    root_pairs = (
        ("root_key_id", root.root_key_id),
        ("designation_id", root.designation_id),
        ("deployment_owner_ref", root.deployment_owner_ref),
        ("designation_digest", root.designation_digest),
    )
    expected_pairs = (
        ("authorization_id", expected.authorization_id),
        ("installation_id", expected.installation_id),
        ("producer_ref", expected.producer_ref),
        ("governance_provenance_digest", expected.governance_provenance_digest),
        ("purpose", expected.purpose),
        ("confirmation_signing_domain", expected.confirmation_signing_domain),
        ("lineage_signing_domain", expected.lineage_signing_domain),
        ("policy_domain", expected.policy_domain),
    )
    if any(
        type(payload[name]) is not type(value) or payload[name] != value
        for name, value in root_pairs
    ):
        raise ValueError("ROOT_SCOPE")
    if any(
        type(payload[name]) is not type(value) or payload[name] != value
        for name, value in expected_pairs
    ):
        raise ValueError("EXPECTED_SCOPE")


def verify_provisioning_authority_history(
    artifacts: tuple[bytes, ...],
    *,
    root: PinnedRootVerifier,
    expected: ExpectedProvisioningAuthorityScope,
) -> ProvisioningAuthorityIntegrityReceipt:
    """Verify the complete root-signed scoped lifecycle supplied by a caller.

    Completeness/current root provenance must be established by a future reviewed
    source adapter.  A receipt is not an Original Confirmation verification,
    CurrentnessWitness, admission, or authorization capability.
    """

    try:
        if type(artifacts) is not tuple or not 0 < len(artifacts) <= MAX_EVENTS:
            raise ValueError("HISTORY")
        _validate_root(root)
        if type(expected) is not ExpectedProvisioningAuthorityScope:
            raise ValueError("EXPECTED")
        expected.__post_init__()

        previous_digest = None
        current_key_id = current_fingerprint = None
        history: list[ProvisioningVerifierHistory] = []
        seen_event_ids: set[str] = set()
        seen_ids: set[str] = set()
        seen_fingerprints: set[str] = set()

        for revision, artifact in enumerate(artifacts, 1):
            payload, signature, canonical_payload, canonical_envelope = _decode_event(artifact)
            _validate_common(payload, root=root, expected=expected)
            if (
                payload["semantic_revision"] != revision
                or payload["previous_event_digest"] != previous_digest
                or payload["event_id"] in seen_event_ids
            ):
                raise ValueError("LINEAGE")
            seen_event_ids.add(payload["event_id"])
            kind = payload["event_kind"]
            old_id = payload["old_verifier_key_id"]
            old_fingerprint = payload["old_verifier_fingerprint"]
            new_id = payload["new_verifier_key_id"]
            new_fingerprint = payload["new_verifier_fingerprint"]

            if revision == 1:
                if (
                    kind != "AUTHORIZE"
                    or old_id is not None
                    or old_fingerprint is not None
                    or new_id is None
                    or new_fingerprint is None
                ):
                    raise ValueError("GENESIS")
            elif kind == "ROTATE":
                if (
                    current_key_id is None
                    or old_id != current_key_id
                    or old_fingerprint != current_fingerprint
                    or new_id is None
                    or new_fingerprint is None
                ):
                    raise ValueError("ROTATE")
            elif kind == "REVOKE":
                if (
                    current_key_id is None
                    or old_id != current_key_id
                    or old_fingerprint != current_fingerprint
                    or new_id is not None
                    or new_fingerprint is not None
                ):
                    raise ValueError("REVOKE")
            else:
                raise ValueError("KIND")

            if new_id is not None and (
                new_id in seen_ids
                or new_fingerprint in seen_fingerprints
                or new_id == current_key_id
                or new_fingerprint == current_fingerprint
            ):
                raise ValueError("KEY_REUSE")

            Ed25519PublicKey.from_public_bytes(root.public_key).verify(
                signature, SIGNATURE_DOMAIN + canonical_payload
            )
            event_digest = _digest(canonical_envelope)

            if current_key_id is not None:
                status = "REVOKED" if kind == "REVOKE" else "SUPERSEDED"
                history[-1] = ProvisioningVerifierHistory(
                    current_key_id, current_fingerprint, status, revision
                )
            if new_id is not None:
                history.append(ProvisioningVerifierHistory(new_id, new_fingerprint, "ACTIVE", None))
                seen_ids.add(new_id)
                seen_fingerprints.add(new_fingerprint)
            current_key_id = new_id
            current_fingerprint = new_fingerprint
            previous_digest = event_digest

        return ProvisioningAuthorityIntegrityReceipt(
            authorization_id=expected.authorization_id,
            installation_id=expected.installation_id,
            producer_ref=expected.producer_ref,
            purpose=expected.purpose,
            semantic_revision=len(artifacts),
            head_event_digest=previous_digest,
            current_verifier_key_id=current_key_id,
            current_verifier_fingerprint=current_fingerprint,
            lifecycle_state="ACTIVE" if current_key_id is not None else "REVOKED",
            verifier_history=tuple(history),
        )
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        RecursionError,
        binascii.Error,
        InvalidSignature,
        UnsupportedAlgorithm,
        rfc8785.CanonicalizationError,
    ):
        raise ProvisioningAuthorityDenied() from None
