"""ADR-078 mathematical event integrity; public receipts are NOT admission witnesses."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import rfc8785
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.bootstrap_authority.contracts import (
    MAX_SAFE_REVISION,
    require_digest,
    require_reference,
    require_revision,
    require_uuid,
)

SCHEMA = "dohamusic/deployment-root-status-event/v1"
DOMAIN = b"DohaMusicDeploymentRootStatusEventV1\x00"
FIELDS = frozenset(
    [
        "schema",
        "algorithm",
        "journal_id",
        "event_id",
        "revision",
        "previous_event_digest",
        "previous_trust_revision",
        "trust_revision",
        "designation_id",
        "deployment_owner_ref",
        "event_kind",
        "old_key_id",
        "old_key_fingerprint",
        "new_key_id",
        "new_key_fingerprint",
        "designation_record_digest",
        "occurred_at",
        "affected_scope_manifest_digest",
        "admission_mode",
    ]
)


class LifecycleIntegrityError(ValueError):
    def __init__(self) -> None:
        super().__init__("LIFECYCLE_INTEGRITY_DENIED")


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE")
        result[key] = value
    return result


def _number(value):
    raise ValueError("NUMBER")


def _read(raw: bytes, limit: int, depth: int):
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise ValueError("SIZE")
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique,
        parse_float=_number,
        parse_constant=_number,
    )

    def check(item, remaining):
        if isinstance(item, (dict, list)):
            if remaining == 0:
                raise ValueError("DEPTH")
            for child in item.values() if isinstance(item, dict) else item:
                check(child, remaining - 1)

    check(value, depth)
    return value


@dataclass(frozen=True, slots=True)
class LifecycleExpectations:
    """Independent PUBLIC expectations, not proof of governance/pin/currentness."""

    journal_id: str
    designation_id: str
    deployment_owner_ref: str
    designation_record_digest: str
    revision: int
    previous_event_digest: str | None
    previous_trust_revision: int
    authoritative_scopes: tuple[tuple[str, str, str], ...]
    public_keys: tuple[tuple[str, bytes], ...]
    checked_at: datetime
    clock_high_water: datetime


@dataclass(frozen=True, slots=True)
class LifecycleIntegrityReceipt:
    """Immutable verified bytes only; can be caller-constructed, never authorizes."""

    canonical_envelope: bytes
    event_digest: str


def verify_lifecycle_integrity(
    artifact: bytes,
    manifest: bytes,
    *,
    expected: LifecycleExpectations,
) -> LifecycleIntegrityReceipt:
    try:
        return _verify(artifact, manifest, expected)
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        RecursionError,
        InvalidSignature,
        UnsupportedAlgorithm,
        rfc8785.CanonicalizationError,
    ):
        raise LifecycleIntegrityError() from None


def _verify(artifact, manifest, expected):
    if type(expected) is not LifecycleExpectations:
        raise ValueError("EXPECTATIONS")
    envelope = _read(artifact, 16_384, 4)
    if type(envelope) is not dict or set(envelope) != {"payload", "signatures"}:
        raise ValueError("ENVELOPE")
    p = envelope["payload"]
    if type(p) is not dict or set(p) != FIELDS:
        raise ValueError("FIELDS")
    if p["schema"] != SCHEMA or p["algorithm"] != "Ed25519":
        raise ValueError("DOMAIN")
    for name in ("journal_id", "event_id", "designation_id"):
        require_uuid(p[name])
    require_reference(p["deployment_owner_ref"])
    for name in ("designation_record_digest", "affected_scope_manifest_digest"):
        require_digest(p[name])
    for name in ("revision", "trust_revision"):
        require_revision(p[name])
    previous = p["previous_trust_revision"]
    if type(previous) is not int or not 0 <= previous < MAX_SAFE_REVISION:
        raise ValueError("REVISION")
    if p["trust_revision"] != previous + 1 or p["revision"] != previous + 1:
        raise ValueError("ORDER")
    kind = p["event_kind"]
    if kind not in {"GENESIS", "NORMAL_ROTATION", "REVOKE", "EXTERNAL_REDESIGNATION"}:
        raise ValueError("KIND")
    genesis = kind == "GENESIS"
    if genesis != (p["revision"] == 1):
        raise ValueError("GENESIS")
    if genesis:
        if p["previous_event_digest"] is not None:
            raise ValueError("PREVIOUS")
    else:
        require_digest(p["previous_event_digest"])
    for side, absent in (("old", genesis), ("new", kind == "REVOKE")):
        if absent:
            if p[f"{side}_key_id"] is not None or p[f"{side}_key_fingerprint"] is not None:
                raise ValueError("KEY")
        else:
            require_reference(p[f"{side}_key_id"])
            require_digest(p[f"{side}_key_fingerprint"])
    if (
        not genesis
        and kind != "REVOKE"
        and (
            p["old_key_id"] == p["new_key_id"]
            or p["old_key_fingerprint"] == p["new_key_fingerprint"]
        )
    ):
        raise ValueError("KEY_REUSE")
    mode = "CROSS_SIGNED_DESIGNATION" if kind == "NORMAL_ROTATION" else "EXTERNAL_DESIGNATION"
    if p["admission_mode"] != mode:
        raise ValueError("MODE")
    for name in (
        "journal_id",
        "designation_id",
        "deployment_owner_ref",
        "designation_record_digest",
        "revision",
        "previous_event_digest",
        "previous_trust_revision",
    ):
        if p[name] != getattr(expected, name):
            raise ValueError("MISMATCH")
    for time in (expected.checked_at, expected.clock_high_water):
        if type(time) is not datetime or time.tzinfo is None or time.utcoffset() != timedelta(0):
            raise ValueError("CLOCK")
    text = p["occurred_at"]
    if type(text) is not str:
        raise ValueError("TIME")
    occurred = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    if occurred.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise ValueError("TIME")
    if not expected.clock_high_water <= expected.checked_at or occurred > expected.checked_at:
        raise ValueError("CLOCK")
    scopes = _read(manifest, 1_048_576, 2)
    if type(scopes) is not list or not 0 < len(scopes) <= 4096:
        raise ValueError("SCOPES")
    tuples = []
    names = ("installation_id", "workspace_id", "existing_owner_id")
    for entry in scopes:
        if type(entry) is not dict or set(entry) != set(names):
            raise ValueError("SCOPE_FIELDS")
        for name in names:
            require_uuid(entry[name])
        tuples.append(tuple(entry[name] for name in names))
    if tuples != sorted(set(tuples)) or tuple(tuples) != expected.authoritative_scopes:
        raise ValueError("SCOPE_MEMBERSHIP")
    if digest(rfc8785.dumps(scopes)) != p["affected_scope_manifest_digest"]:
        raise ValueError("MANIFEST_DIGEST")
    keys = dict(expected.public_keys)
    if len(keys) != len(expected.public_keys):
        raise ValueError("DUPLICATE_KEY")
    for side in ("old", "new"):
        key_id = p[f"{side}_key_id"]
        if key_id is not None:
            public = keys[key_id]
            if type(public) is not bytes or len(public) != 32:
                raise ValueError("PUBLIC_KEY")
            if digest(public) != p[f"{side}_key_fingerprint"]:
                raise ValueError("FINGERPRINT")
    required = (
        [p["old_key_id"], p["new_key_id"]]
        if kind == "NORMAL_ROTATION"
        else [p["old_key_id"] if kind == "REVOKE" else p["new_key_id"]]
    )
    signatures = envelope["signatures"]
    if type(signatures) is not list or len(signatures) != len(required):
        raise ValueError("SIGNATURES")
    signer_ids = []
    for item in signatures:
        if type(item) is not dict or set(item) != {"signer_key_id", "signature"}:
            raise ValueError("SIGNATURE_FIELDS")
        signer_ids.append(item["signer_key_id"])
    if signer_ids != sorted(required):
        raise ValueError("SIGNERS")
    message = DOMAIN + rfc8785.dumps(p)
    for item in signatures:
        text = item["signature"]
        if type(text) is not str or len(text) != 86:
            raise ValueError("SIGNATURE_ENCODING")
        signature = base64.b64decode(text + "==", altchars=b"-_", validate=True)
        if (
            len(signature) != 64
            or base64.urlsafe_b64encode(signature).rstrip(b"=").decode() != text
        ):
            raise ValueError("SIGNATURE_ENCODING")
        Ed25519PublicKey.from_public_bytes(keys[item["signer_key_id"]]).verify(signature, message)
    canonical = rfc8785.dumps(envelope)
    return LifecycleIntegrityReceipt(canonical, digest(canonical))
