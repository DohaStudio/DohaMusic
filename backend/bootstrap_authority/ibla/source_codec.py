"""ADR-110 canonical comparison/crypto only; this module cannot mint authority."""

import base64
from datetime import UTC, datetime, timedelta

import rfc8785
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from backend.bootstrap_authority.approval_verifier import SIGNATURE_TEXT, _timestamp
from backend.bootstrap_authority.contracts import (
    require_digest,
    require_reference,
    require_revision,
    require_uuid,
)
from backend.bootstrap_authority.ibla.contracts import IblaDenied, IblaInconsistent
from backend.bootstrap_authority.lifecycle_verifier import _read, digest

ANCHOR_DOMAIN = b"DohaMusicIblaCommissioningAnchorV1\x00"
CONFIRMATION_DOMAIN = b"DohaMusicIblaInitializerConfirmationV1\x00"
INVENTORY_DOMAIN = b"DohaMusicIblaScopeInventoryV1\x00"
MAPPING_DOMAIN = b"DohaMusicIblaCommissioningMappingV1\x00"
CUSTODY_DOMAIN = b"DohaMusicIblaCustodyComparisonV1\x00"
POSSESSION_DOMAIN = b"DohaMusicIblaInstallationPossessionV1\x00"
ANCHOR_FIELDS = frozenset(
    [
        "schema",
        "algorithm",
        "purpose",
        "anchor_id",
        "domain_id",
        "deployment_id",
        "installation_id",
        "installation_proof_digest",
        "lineage_id",
        "journal_id",
        "ledger_id",
        "checkpoint_id",
        "designation_id",
        "designation_digest",
        "root_key_id",
        "root_fingerprint",
        "authority_epoch",
        "commissioning_action_id",
        "governance_provenance_ref",
        "governance_provenance_digest",
        "positive_origin_ref",
        "positive_origin_digest",
        "inventory",
        "inventory_digest",
        "initializer_ref",
        "initializer_key_id",
        "initializer_fingerprint",
        "ledger_custodian_ref",
        "checkpoint_keeper_ref",
        "commissioning_mapping_digest",
        "custody_provisioning_digest",
        "issued_at",
        "not_before",
        "expires_at",
    ]
)
CONFIRMATION_FIELDS = frozenset(
    [
        "schema",
        "algorithm",
        "purpose",
        "confirmation_id",
        "commissioning_action_id",
        "anchor_digest",
        "designation_id",
        "designation_digest",
        "initializer_ref",
        "initializer_key_id",
        "initializer_fingerprint",
        "positive_origin_ref",
        "positive_origin_digest",
        "inventory_digest",
        "commissioning_mapping_digest",
        "custody_provisioning_digest",
        "original_confirmation_ref",
        "original_confirmation_digest",
        "issued_at",
        "not_before",
        "expires_at",
    ]
)
INVENTORY_FIELDS = frozenset(
    [
        "schema",
        "domain_id",
        "deployment_id",
        "lineage_id",
        "installation_id",
        "installation_proof_digest",
        "journal_id",
        "coverage_start_ref",
        "coverage_start_digest",
        "positive_origin_ref",
        "positive_origin_digest",
        "scopes",
        "installation_aliases",
        "lineage_aliases",
        "journal_aliases",
        "imported_scope_refs",
        "external_history",
    ]
)
MAPPING_FIELDS = tuple(
    [
        "domain_id",
        "anchor_id",
        "ledger_id",
        "checkpoint_id",
        "deployment_id",
        "installation_id",
        "installation_proof_digest",
        "lineage_id",
        "journal_id",
        "designation_digest",
        "authority_epoch",
        "commissioning_action_id",
        "ledger_custodian_ref",
        "checkpoint_keeper_ref",
    ]
)
SCOPE_FIELDS = ("installation_id", "workspace_id", "existing_owner_id")
ARRAY_FIELDS = {
    "installation_aliases": ("installation_id", "installation_proof_digest", "lineage_id"),
    "lineage_aliases": ("lineage_id", "domain_id"),
    "journal_aliases": ("journal_id", "lineage_id"),
    "imported_scope_refs": ("ref", "digest"),
    "external_history": ("record_ref", "record_digest", "fact_kind", "affected_scopes"),
}


def comparison(domain, payload):
    return digest(domain + rfc8785.dumps(payload))


def original(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 1_048_576:
        raise IblaDenied()
    try:
        text = raw.decode("utf-8", errors="strict")
        if not text.strip() or "\x00" in text or text.startswith("\ufeff"):
            raise ValueError()
        return digest(raw)
    except (ValueError, UnicodeError):
        raise IblaInconsistent() from None


def _scalar(key, value):
    if key == "authority_epoch":
        require_revision(value)
    elif type(value) is not str:
        raise ValueError()
    elif key.endswith(("_digest", "_fingerprint")) or key == "digest":
        require_digest(value)
    elif key.endswith("_key_id") or key.endswith("_ref") or key == "ref":
        require_reference(value)
    elif key.endswith("_id"):
        require_uuid(value)


def _scopes(value):
    if type(value) is not list or not 0 < len(value) <= 4096:
        raise IblaDenied()
    tuples = []
    for row in value:
        if type(row) is not dict or set(row) != set(SCOPE_FIELDS):
            raise ValueError()
        for key, item in row.items():
            _scalar(key, item)
        tuples.append(tuple(row[key] for key in SCOPE_FIELDS))
    if tuples != sorted(set(tuples)):
        raise ValueError()
    return tuple(tuples)


def inventory(value):
    if type(value) is not dict or set(value) != INVENTORY_FIELDS:
        raise IblaDenied()
    if value["schema"] != "dohamusic/ibla-scope-inventory/v1":
        raise IblaDenied()
    for key, item in value.items():
        if key not in ARRAY_FIELDS and key != "scopes":
            _scalar(key, item)
    scopes = _scopes(value["scopes"])
    for name, fields in ARRAY_FIELDS.items():
        rows = value[name]
        if type(rows) is not list or len(rows) > 4096:
            raise IblaDenied()
        encoded = []
        for row in rows:
            if type(row) is not dict or set(row) != set(fields):
                raise ValueError()
            for key, item in row.items():
                if key == "affected_scopes":
                    _scopes(item)
                else:
                    _scalar(key, item)
            encoded.append(rfc8785.dumps(row))
        if encoded != sorted(set(encoded)):
            raise ValueError()
    return scopes


def signature(raw):
    if type(raw) is not str or not SIGNATURE_TEXT.fullmatch(raw):
        raise ValueError()
    result = base64.b64decode(raw + "==", altchars=b"-_", validate=True)
    if len(result) != 64 or base64.urlsafe_b64encode(result).rstrip(b"=").decode() != raw:
        raise ValueError()
    return result


def verify_signature(public, fingerprint, message, supplied):
    if type(public) is not bytes or len(public) != 32 or digest(public) != fingerprint:
        raise IblaInconsistent()
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature(supplied), message)
    except UnsupportedAlgorithm:
        raise IblaDenied() from None
    except (ValueError, InvalidSignature):
        raise IblaInconsistent() from None


def signed(raw, *, confirmation, public, fingerprint, checked_at):
    """Return validated public payload plus digest/expiry; NOT authentic source evidence."""
    limit = 16_384 if confirmation else 1_048_576
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise IblaDenied()
    try:
        envelope = _read(raw, limit, 8)
        if (
            type(envelope) is not dict
            or set(envelope) != {"payload", "signature"}
            or rfc8785.dumps(envelope) != raw
        ):
            raise ValueError()
        p = envelope["payload"]
        fields = CONFIRMATION_FIELDS if confirmation else ANCHOR_FIELDS
        if type(p) is not dict or set(p) != fields:
            raise ValueError()
        for key, value in p.items():
            if key != "inventory":
                _scalar(key, value)
        schema = "initializer-confirmation" if confirmation else "commissioning-anchor"
        purpose = (
            "IBLA_COMMISSIONING_CONFIRMATION_ONLY" if confirmation else "IBLA_COMMISSIONING_ONLY"
        )
        if p["schema"] != f"dohamusic/ibla-{schema}/v1":
            raise IblaDenied()
        if p["algorithm"] != "Ed25519" or p["purpose"] != purpose:
            raise ValueError()
        issued, start, end = (_timestamp(p[k]) for k in ("issued_at", "not_before", "expires_at"))
        if (
            type(checked_at) is not datetime
            or checked_at.tzinfo is not UTC
            or not issued <= start < end
            or end - issued > timedelta(hours=24)
            or not issued <= checked_at
            or not start <= checked_at < end
        ):
            raise ValueError()
        domain = CONFIRMATION_DOMAIN if confirmation else ANCHOR_DOMAIN
        message = domain + rfc8785.dumps(p)
        verify_signature(public, fingerprint, message, envelope["signature"])
        if not confirmation:
            inventory(p["inventory"])
            if comparison(INVENTORY_DOMAIN, p["inventory"]) != p["inventory_digest"]:
                raise ValueError()
        return p, digest(message), end
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise IblaInconsistent() from None
