"""Bounded canonical public facts. Digests do not authenticate commissioning."""

from dataclasses import asdict
from datetime import UTC, datetime

import rfc8785

from backend.bootstrap_authority.contracts import require_digest, require_uuid
from backend.bootstrap_authority.ibla.contracts import Binding, Event, Head
from backend.bootstrap_authority.lifecycle_verifier import _read, digest

LIMIT = 16384
EVENT_SCHEMA = "dohamusic/ibla-ledger-event/v1"
CONTROL_SCHEMA = "dohamusic/ibla-checkpoint-control/v1"
EVENT_DOMAIN = b"DohaMusicIblaLedgerEventV1\x00"
CONTROL_DOMAIN = b"DohaMusicIblaCheckpointControlV1\x00"
OPERATION_DOMAIN = b"DohaMusicIblaOperationV1\x00"
# Unsupported future authorization/rotation/alias kinds fail closed.
KINDS = frozenset({"COMMISSION", "HISTORY_BLOCK", "RETIRE"})


def require_audit_time(value):
    # Same canonical UTC-second profile as the existing lifecycle verifier.
    # This is an audit fact, never a freshness, clock trust or permission check.
    if type(value) is not str:
        raise ValueError("AUDIT_TIME")
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("AUDIT_TIME")


def canonical(raw, *, version=1):
    value = _read(raw, LIMIT, 6 if version == 2 else 4)
    if type(value) is not dict or rfc8785.dumps(value) != raw:
        raise ValueError("CANONICAL")
    return value


def binding_wire(binding):
    if type(binding) is not Binding:
        raise ValueError("BINDING")
    binding.validate()
    return rfc8785.dumps(asdict(binding))


def encode_event(binding, *, event_id, operation_id, expected, kind, evidence_digest, recorded_at):
    binding_wire(binding)
    if type(expected) is not Head:
        raise ValueError("HEAD")
    expected.validate()
    payload = dict(
        schema=EVENT_SCHEMA,
        binding=asdict(binding),
        event_id=event_id,
        operation_id=operation_id,
        revision=expected.revision + 1,
        previous_digest=expected.digest,
        kind=kind,
        evidence_digest=evidence_digest,
        recorded_at=recorded_at,
    )
    wire = rfc8785.dumps(payload)
    parse_event(wire, binding)
    return wire


def parse_event(raw, binding, *, version=1):
    binding_wire(binding)
    p = canonical(raw, version=version)
    if version == 2 and p.get("schema") == "dohamusic/ibla-ledger-event/v2":
        from backend.bootstrap_authority.ibla.registration_codec import parse_event as registration

        return registration(raw, binding)
    if set(p) != {
        "schema",
        "binding",
        "event_id",
        "operation_id",
        "revision",
        "previous_digest",
        "kind",
        "evidence_digest",
        "recorded_at",
    }:
        raise ValueError("FIELDS")
    if p["schema"] != EVENT_SCHEMA or p["binding"] != asdict(binding):
        raise ValueError("BINDING")
    # Canonical equality alone permits Python bool/int equality; check nested types too.
    if type(p["binding"]) is not dict:
        raise ValueError("BINDING")
    Binding(**p["binding"]).validate()
    for key in ("event_id", "operation_id"):
        if type(p[key]) is not str:
            raise ValueError("IDENTITY")
        require_uuid(p[key])
    if type(p["evidence_digest"]) is not str:
        raise ValueError("EVIDENCE")
    require_digest(p["evidence_digest"])
    require_audit_time(p["recorded_at"])
    head = Head(p["revision"], digest(EVENT_DOMAIN + raw))
    head.validate()
    previous = Head(head.revision - 1, p["previous_digest"])
    previous.validate()
    if type(p["kind"]) is not str or p["kind"] not in KINDS:
        raise ValueError("KIND")
    if (p["kind"] == "COMMISSION") != (head.revision == 1):
        raise ValueError("ORIGIN")
    return Event(
        head.revision,
        p["event_id"],
        p["operation_id"],
        digest(OPERATION_DOMAIN + raw),
        p["previous_digest"],
        head.digest,
        p["kind"],
        raw,
    )


def control_wire(binding, *, sequence, previous, kind, confirmed, pending, recorded_at, version=1):
    return rfc8785.dumps(
        dict(
            schema=CONTROL_SCHEMA if version == 1 else "dohamusic/ibla-checkpoint-control/v2",
            binding=asdict(binding),
            sequence=sequence,
            previous_digest=previous,
            kind=kind,
            confirmed=asdict(confirmed),
            pending=canonical(pending, version=version),
            recorded_at=recorded_at,
        )
    )


def parse_control(raw, binding, *, version=1):
    binding_wire(binding)
    p = canonical(raw, version=version)
    v2 = p.get("schema") == "dohamusic/ibla-checkpoint-control/v2"
    domain = b"DohaMusicIblaCheckpointControlV2\x00" if v2 else CONTROL_DOMAIN
    if set(p) != {
        "schema",
        "binding",
        "sequence",
        "previous_digest",
        "kind",
        "confirmed",
        "pending",
        "recorded_at",
    } or p["schema"] not in (
        {CONTROL_SCHEMA, "dohamusic/ibla-checkpoint-control/v2"}
        if version == 2
        else {CONTROL_SCHEMA}
    ):
        raise ValueError("CONTROL")
    if p["binding"] != asdict(binding):
        raise ValueError("BINDING")
    Binding(**p["binding"]).validate()
    require_audit_time(p["recorded_at"])
    Head(p["sequence"], digest(domain + raw)).validate()
    Head(p["sequence"] - 1, p["previous_digest"]).validate()
    confirmed = Head(**p["confirmed"])
    confirmed.validate()
    candidate = parse_event(rfc8785.dumps(p["pending"]), binding, version=2 if v2 else 1)
    if p["kind"] not in {"COMMISSIONING_PENDING", "PREPARED", "CONFIRMED", "UNCERTAIN"}:
        raise ValueError("STATE")
    return p, confirmed, candidate, digest(domain + raw)
