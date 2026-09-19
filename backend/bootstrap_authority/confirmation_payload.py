"""Canonical original-confirmation payload boundary, never authenticity/currentness."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from enum import StrEnum

import rfc8785

from backend.bootstrap_authority.contracts import require_digest, require_reference, require_uuid
from backend.bootstrap_authority.lifecycle_verifier import digest

CONFIRMATION_SCHEMA = "dohamusic/original-initializer-confirmation/v1"
CONFIRMATION_SCOPE = "INSTALLATION_POLICY_PROVISIONING_ONLY"
CONFIRMATION_ALGORITHM = "Ed25519"
MAX_CONFIRMATION_BYTES = 1_048_576
PAYLOAD_FIELDS = frozenset(
    {
        "schema",
        "algorithm",
        "confirmation_id",
        "original_confirmation_ref",
        "initializer_ref",
        "installation_id",
        "installation_proof_key_fingerprint",
        "action_id",
        "policy_digest",
        "designation_digest",
        "scope",
        "verifier_key_id",
        "verifier_fingerprint",
        "replay_id",
    }
)


class ConfirmationPayloadErrorCode(StrEnum):
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    NON_CANONICAL_PAYLOAD = "NON_CANONICAL_PAYLOAD"
    EXPECTATION_MISMATCH = "EXPECTATION_MISMATCH"


class ConfirmationPayloadDenied(ValueError):
    def __init__(self, code: ConfirmationPayloadErrorCode):
        self.code = code
        super().__init__(code.value)


def _reject_number(value: str):
    raise ValueError("JSON_NUMBER_NOT_ALLOWED")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True, repr=False)
class ExpectedConfirmationPayload:
    """Independent public expectations; construction is not trusted provisioning."""

    confirmation_id: str
    original_confirmation_ref: str
    initializer_ref: str
    installation_id: str
    installation_proof_key_fingerprint: str
    action_id: str
    policy_digest: str
    designation_digest: str
    verifier_key_id: str
    verifier_fingerprint: str
    replay_id: str

    def __post_init__(self):
        values = tuple(getattr(self, item.name) for item in fields(self))
        if any(type(value) is not str for value in values):
            raise ValueError("INVALID_EXPECTATION_TYPE")
        for value in (self.confirmation_id, self.installation_id, self.action_id, self.replay_id):
            require_uuid(value)
        for value in (self.original_confirmation_ref, self.initializer_ref, self.verifier_key_id):
            require_reference(value)
        for value in (
            self.installation_proof_key_fingerprint,
            self.policy_digest,
            self.designation_digest,
            self.verifier_fingerprint,
        ):
            require_digest(value)


@dataclass(frozen=True, slots=True, repr=False)
class ConfirmationPayloadBoundary:
    """Canonical byte binding only; not a signature receipt, witness or permission."""

    confirmation_id: str
    replay_id: str
    verifier_fingerprint: str
    payload_digest: str


def parse_canonical_confirmation_payload(
    raw: bytes, *, expected: ExpectedConfirmationPayload
) -> ConfirmationPayloadBoundary:
    """Parse exact JCS bytes and compare independent expectations, fail closed."""

    if type(expected) is not ExpectedConfirmationPayload:
        raise ConfirmationPayloadDenied(ConfirmationPayloadErrorCode.EXPECTATION_MISMATCH)
    try:
        expected.__post_init__()
    except (TypeError, ValueError):
        raise ConfirmationPayloadDenied(ConfirmationPayloadErrorCode.EXPECTATION_MISMATCH) from None
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_CONFIRMATION_BYTES:
            raise ValueError("INVALID_SIZE")
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_int=_reject_number,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if type(payload) is not dict or set(payload) != PAYLOAD_FIELDS:
            raise ValueError("INVALID_FIELDS")
        if any(type(value) is not str for value in payload.values()):
            raise ValueError("INVALID_VALUE_TYPE")
        if (
            payload["schema"] != CONFIRMATION_SCHEMA
            or payload["algorithm"] != CONFIRMATION_ALGORITHM
            or payload["scope"] != CONFIRMATION_SCOPE
        ):
            raise ValueError("INVALID_DOMAIN")
        for key in ("confirmation_id", "installation_id", "action_id", "replay_id"):
            require_uuid(payload[key])
        for key in ("original_confirmation_ref", "initializer_ref", "verifier_key_id"):
            require_reference(payload[key])
        for key in (
            "installation_proof_key_fingerprint",
            "policy_digest",
            "designation_digest",
            "verifier_fingerprint",
        ):
            require_digest(payload[key])
        canonical = rfc8785.dumps(payload)
    except (ValueError, UnicodeError, RecursionError, rfc8785.CanonicalizationError):
        raise ConfirmationPayloadDenied(ConfirmationPayloadErrorCode.MALFORMED_PAYLOAD) from None
    if canonical != raw:
        raise ConfirmationPayloadDenied(ConfirmationPayloadErrorCode.NON_CANONICAL_PAYLOAD)
    if any(payload[item.name] != getattr(expected, item.name) for item in fields(expected)):
        raise ConfirmationPayloadDenied(ConfirmationPayloadErrorCode.EXPECTATION_MISMATCH)
    return ConfirmationPayloadBoundary(
        confirmation_id=expected.confirmation_id,
        replay_id=expected.replay_id,
        verifier_fingerprint=expected.verifier_fingerprint,
        payload_digest=digest(raw),
    )
