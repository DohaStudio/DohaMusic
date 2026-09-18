"""Strict ADR-076 Ed25519/JCS issuance integrity, deliberately without authorization."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import rfc8785
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.bootstrap_authority.contracts import (
    ApprovalIntegrityReceipt,
    ExpectedApprovalScope,
    PinnedRootVerifier,
    require_digest,
    require_reference,
    require_revision,
    require_uuid,
)

APPROVAL_SCHEMA = "dohamusic/deployment-bootstrap-approval/v1"
SIGNATURE_DOMAIN = b"DohaMusicDeploymentBootstrapApprovalV1\x00"
MAX_ARTIFACT_BYTES = 16_384
PAYLOAD_FIELDS = frozenset(
    {
        "schema",
        "algorithm",
        "approval_id",
        "designation_id",
        "deployment_owner_ref",
        "designation_digest",
        "root_key_id",
        "installation_id",
        "installation_proof_key_fingerprint",
        "workspace_id",
        "existing_owner_id",
        "assignment_id",
        "assignment_revision",
        "custodian_ref",
        "custodian_proof_key_fingerprint",
        "scope",
        "issued_at",
        "not_before",
        "expires_at",
        "governance_provenance_digest",
    }
)
CANONICAL_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", re.ASCII)
SIGNATURE_TEXT = re.compile(r"[A-Za-z0-9_-]{86}\Z", re.ASCII)


class ApprovalIntegrityErrorCode(StrEnum):
    MALFORMED_ARTIFACT = "MALFORMED_ARTIFACT"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    ROOT_MISMATCH = "ROOT_MISMATCH"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    INVALID_CHECK_TIME = "INVALID_CHECK_TIME"
    OUTSIDE_ISSUANCE_WINDOW = "OUTSIDE_ISSUANCE_WINDOW"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    VERIFIER_UNAVAILABLE = "VERIFIER_UNAVAILABLE"


class ApprovalIntegrityError(ValueError):
    """Safe diagnostic code only, never attacker payload or cryptographic material."""

    def __init__(self, code: ApprovalIntegrityErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _reject_number(value: str) -> None:
    raise ValueError("INVALID_JSON_NUMBER")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _read_envelope(artifact: bytes) -> tuple[dict[str, object], bytes]:
    try:
        if type(artifact) is not bytes or not 0 < len(artifact) <= MAX_ARTIFACT_BYTES:
            raise ValueError("INVALID_SIZE")
        envelope = json.loads(
            artifact.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
            raise ValueError("INVALID_ENVELOPE")
        payload = envelope["payload"]
        signature_text = envelope["signature"]
        if type(payload) is not dict or set(payload) != PAYLOAD_FIELDS:
            raise ValueError("INVALID_FIELDS")
        if not isinstance(signature_text, str) or not SIGNATURE_TEXT.fullmatch(signature_text):
            raise ValueError("INVALID_SIGNATURE_ENCODING")
        signature = base64.b64decode(signature_text + "==", altchars=b"-_", validate=True)
        if (
            len(signature) != 64
            or base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii") != signature_text
        ):
            raise ValueError("NON_CANONICAL_SIGNATURE")
        return payload, signature
    except (ValueError, UnicodeError, RecursionError, binascii.Error):
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.MALFORMED_ARTIFACT) from None


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not CANONICAL_TIME.fullmatch(value):
        raise ValueError("INVALID_TIMESTAMP")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _validate_payload(payload: dict[str, object]) -> tuple[bytes, datetime, datetime, datetime]:
    try:
        for key, value in payload.items():
            if key == "assignment_revision":
                require_revision(value)
            elif not isinstance(value, str):
                raise ValueError("INVALID_FIELD_TYPE")
            elif key.endswith("_fingerprint") or key.endswith("_digest"):
                require_digest(value)
            elif key in {"root_key_id", "deployment_owner_ref", "custodian_ref"}:
                require_reference(value)
            elif key.endswith("_id"):
                require_uuid(value)
        if (
            payload["schema"] != APPROVAL_SCHEMA
            or payload["algorithm"] != "Ed25519"
            or payload["scope"] != "FIRST_OWNER_BINDING_ONLY"
        ):
            raise ValueError("INVALID_DOMAIN_ALGORITHM_SCOPE")
        issued = _timestamp(payload["issued_at"])
        not_before = _timestamp(payload["not_before"])
        expires = _timestamp(payload["expires_at"])
        if not issued <= not_before < expires or expires - issued > timedelta(hours=24):
            raise ValueError("INVALID_WINDOW")
        return rfc8785.dumps(payload), issued, not_before, expires
    except (ValueError, UnicodeError, rfc8785.CanonicalizationError):
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.INVALID_PAYLOAD) from None


def verify_issuance_integrity(
    artifact: bytes,
    *,
    root: PinnedRootVerifier,
    expected_scope: ExpectedApprovalScope,
    checked_at: datetime,
) -> ApprovalIntegrityReceipt:
    """Verify an immutable issuance artifact against independent PUBLIC expectations.

    This function does not prove trusted provisioning/current root status, approval or
    assignment eligibility, fresh proof possession, target authentication, history or
    external journal freshness. No runtime consumer is wired to this receipt.
    """

    if type(root) is not PinnedRootVerifier or type(expected_scope) is not ExpectedApprovalScope:
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.INVALID_PAYLOAD)
    if (
        type(checked_at) is not datetime
        or checked_at.tzinfo is None
        or checked_at.utcoffset() != timedelta(0)
    ):
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.INVALID_CHECK_TIME)
    payload, signature = _read_envelope(artifact)
    canonical, issued, not_before, expires = _validate_payload(payload)
    if "sha256:" + hashlib.sha256(root.public_key).hexdigest() != root.public_key_fingerprint:
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.ROOT_MISMATCH)
    for key in ("root_key_id", "designation_id", "deployment_owner_ref", "designation_digest"):
        if payload[key] != getattr(root, key):
            raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.ROOT_MISMATCH)
    if any(
        payload[item.name] != getattr(expected_scope, item.name) for item in fields(expected_scope)
    ):
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.SCOPE_MISMATCH)
    if not issued <= checked_at or not not_before <= checked_at < expires:
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.OUTSIDE_ISSUANCE_WINDOW)
    try:
        Ed25519PublicKey.from_public_bytes(root.public_key).verify(
            signature, SIGNATURE_DOMAIN + canonical
        )
    except (InvalidSignature, ValueError):
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.INVALID_SIGNATURE) from None
    except UnsupportedAlgorithm:
        raise ApprovalIntegrityError(ApprovalIntegrityErrorCode.VERIFIER_UNAVAILABLE) from None
    return ApprovalIntegrityReceipt(
        approval_id=expected_scope.approval_id,
        assignment_id=expected_scope.assignment_id,
        assignment_revision=expected_scope.assignment_revision,
        payload_digest="sha256:" + hashlib.sha256(canonical).hexdigest(),
        checked_at=checked_at.astimezone(UTC),
        expires_at=expires,
    )
