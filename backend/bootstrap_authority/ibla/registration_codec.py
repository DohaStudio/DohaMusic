"""ADR-111 bounded comparison wire; signatures and facts never grant a write."""

from dataclasses import asdict
from datetime import timedelta

import rfc8785

from backend.bootstrap_authority.approval_verifier import _timestamp
from backend.bootstrap_authority.contracts import require_digest, require_reference, require_uuid
from backend.bootstrap_authority.ibla.codec import binding_wire, require_audit_time
from backend.bootstrap_authority.ibla.contracts import Binding, Event, Head
from backend.bootstrap_authority.ibla.source_codec import verify_signature
from backend.bootstrap_authority.lifecycle_verifier import _read, digest

INTENT_DOMAIN = b"DohaMusicIblaRegistrationIntentV1\x00"
CONFIRMATION_DOMAIN = b"DohaMusicIblaRegistrationConfirmationV1\x00"
SCOPE_DOMAIN = b"DohaMusicIblaRegistrationScopeV1\x00"
EVENT_DOMAIN = b"DohaMusicIblaLedgerEventV2\x00"
OPERATION_DOMAIN = b"DohaMusicIblaOperationV2\x00"
PURPOSE = "IBLA_REGISTRATION_COMMIT_ONLY"
REGISTRATION_FIELDS = frozenset(
    {
        "registration_id",
        "purpose",
        "inventory_digest",
        "registration_scope_digest",
        "intended_journal_id",
        "expected_l_head",
        "expected_h_head",
        "expected_h_confirmed",
        "writer_ref",
        "initializer_ref",
        "root_key_id",
        "initializer_key_id",
        "intent_digest",
        "confirmation_digest",
        "commissioning_confirmation_digest",
        "positive_origin_digest",
        "observation_id",
    }
)
INTENT_FIELDS = (
    REGISTRATION_FIELDS
    - {
        "intent_digest",
        "confirmation_digest",
        "observation_id",
    }
) | {"schema", "operation_id", "binding", "issued_at", "expires_at", "recorded_at"}
CONFIRMATION_FIELDS = frozenset(
    {
        "schema",
        "purpose",
        "intent_digest",
        "initializer_ref",
        "initializer_key_id",
        "original_confirmation_ref",
        "original_confirmation_digest",
        "issued_at",
        "expires_at",
    }
)
EVENT_FIELDS = frozenset(
    {
        "schema",
        "binding",
        "event_id",
        "operation_id",
        "revision",
        "previous_digest",
        "kind",
        "evidence_digest",
        "recorded_at",
        "registration",
    }
)


def canonical(raw, limit=8192):
    p = _read(raw, limit, 6)
    if type(p) is not dict or rfc8785.dumps(p) != raw:
        raise ValueError("REGISTRATION_WIRE")
    return p


def reference(value):
    if type(value) is not str or not 1 <= len(value.encode("ascii")) <= 128:
        raise ValueError("REGISTRATION_REFERENCE")
    require_reference(value)


def head(value):
    if type(value) is not dict or set(value) != {"revision", "digest"}:
        raise ValueError("REGISTRATION_HEAD")
    h = Head(**value)
    h.validate()
    if h.revision == 0:
        raise ValueError("REGISTRATION_HEAD")
    return h


def _registration(p):
    if type(p) is not dict or set(p) != REGISTRATION_FIELDS or p["purpose"] != PURPOSE:
        raise ValueError("REGISTRATION_FIELDS")
    for k, v in p.items():
        if k.endswith("_head") or k == "expected_h_confirmed":
            head(v)
        elif k.endswith("_digest"):
            if type(v) is not str:
                raise ValueError("REGISTRATION_DIGEST")
            require_digest(v)
        elif k.endswith("_ref") or k.endswith("_key_id"):
            reference(v)
        elif k.endswith("_id"):
            if type(v) is not str:
                raise ValueError("REGISTRATION_ID")
            require_uuid(v)
    if (
        head(p["expected_l_head"]).revision != 1
        or p["expected_h_confirmed"] != p["expected_l_head"]
    ):
        raise ValueError("REGISTRATION_PREDECESSOR")


def parse_event(raw, binding):
    binding_wire(binding)
    p = canonical(raw)
    if (
        set(p) != EVENT_FIELDS
        or p["schema"] != "dohamusic/ibla-ledger-event/v2"
        or p["kind"] != "REGISTRATION_COMMITTED"
        or p["binding"] != asdict(binding)
    ):
        raise ValueError("REGISTRATION_EVENT")
    Binding(**p["binding"]).validate()
    _registration(p["registration"])
    r = p["registration"]
    for k in ("event_id", "operation_id"):
        if type(p[k]) is not str:
            raise ValueError("REGISTRATION_ID")
        require_uuid(p[k])
    require_audit_time(p["recorded_at"])
    h = Head(p["revision"], digest(EVENT_DOMAIN + raw))
    h.validate()
    if (
        h.revision != 2
        or p["event_id"] != r["registration_id"]
        or p["operation_id"] == p["event_id"]
        or p["previous_digest"] != r["expected_l_head"]["digest"]
        or p["evidence_digest"] != r["intent_digest"]
    ):
        raise ValueError("REGISTRATION_CORRELATION")
    return Event(
        2,
        p["event_id"],
        p["operation_id"],
        digest(OPERATION_DOMAIN + raw),
        p["previous_digest"],
        h.digest,
        p["kind"],
        raw,
    )


def signed(raw, *, confirmation, public, fingerprint, checked_at):
    envelope = canonical(raw, 16384)
    if set(envelope) != {"payload", "signature"}:
        raise ValueError("REGISTRATION_ENVELOPE")
    p = envelope["payload"]
    if type(p) is not dict or set(p) != (CONFIRMATION_FIELDS if confirmation else INTENT_FIELDS):
        raise ValueError("REGISTRATION_FIELDS")
    wire = rfc8785.dumps(p)
    if len(wire) > (4096 if confirmation else 8192):
        raise ValueError("REGISTRATION_SIZE")
    schema = "confirmation" if confirmation else "intent"
    purpose = "IBLA_REGISTRATION_CONFIRMATION_ONLY" if confirmation else PURPOSE
    if p["schema"] != f"dohamusic/ibla-registration-{schema}/v1" or p["purpose"] != purpose:
        raise ValueError("REGISTRATION_PURPOSE")
    for k, v in p.items():
        if k.endswith("_ref") or k.endswith("_key_id"):
            reference(v)
        elif k.endswith("_digest"):
            if type(v) is not str:
                raise ValueError("REGISTRATION_DIGEST")
            require_digest(v)
        elif k.endswith("_id"):
            if type(v) is not str:
                raise ValueError("REGISTRATION_ID")
            require_uuid(v)
    for k in ("issued_at", "expires_at"):
        require_audit_time(p[k])
    start, end = _timestamp(p["issued_at"]), _timestamp(p["expires_at"])
    if not start <= checked_at < end or not timedelta(0) < end - start <= timedelta(hours=24):
        raise ValueError("REGISTRATION_VALIDITY")
    if not confirmation:
        Binding(**p["binding"]).validate()
        for k in ("expected_l_head", "expected_h_head", "expected_h_confirmed"):
            head(p[k])
        if (
            p["recorded_at"] != p["issued_at"]
            or p["registration_id"] == p["operation_id"]
            or head(p["expected_l_head"]).revision != 1
            or p["expected_h_confirmed"] != p["expected_l_head"]
        ):
            raise ValueError("REGISTRATION_INTENT")
    domain = CONFIRMATION_DOMAIN if confirmation else INTENT_DOMAIN
    verify_signature(public, fingerprint, domain + wire, envelope["signature"])
    return p, digest(domain + wire), end
