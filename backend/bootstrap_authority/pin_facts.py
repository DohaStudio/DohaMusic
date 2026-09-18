"""Complete NON-AUTHORIZING pin comparison codec, not provisioning/currentness.

The separate private-file transport is a future reviewed adapter's input only.
Even matching facts do not prove designation, possession or durable journal history.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import rfc8785

from backend.bootstrap_authority.contracts import require_digest, require_uuid
from backend.bootstrap_authority.journal_repository import JournalHead
from backend.bootstrap_authority.lifecycle_verifier import _read
from backend.bootstrap_authority.witness_lifetime import CurrentnessBinding, WitnessLifetimeDenied

PIN_FACTS_SCHEMA = "dohamusic/private-pin-comparison-facts/v1"
MAX_PIN_FACTS = 1_048_576
FIELDS = frozenset(
    (
        "schema",
        "installation_id",
        "installation_proof_key_fingerprint",
        "pin",
        "designation_id",
        "designation_record_digest",
        "deployment_owner_ref",
        "affected_scopes",
        "root_key_id",
        "root_fingerprint",
        "root_public_key",
        "status",
        "domain",
    )
)
HEAD_FIELDS = frozenset(
    ("journal_id", "revision", "trust_revision", "head_digest", "current_key_id", "last_key_id")
)
SCOPE_FIELDS = ("installation_id", "workspace_id", "existing_owner_id")


class PrivateFactsDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("DEPLOYMENT_PRIVATE_FACTS_DENIED")


@dataclass(frozen=True, slots=True, repr=False)
class PinComparisonFacts:
    """Public immutable facts only; constructor/equality/file source is NOT permission.

    binding.journal comes from external expectations, NOT this file. The file only
    supplies its pin. Independent fresh authoritative history MUST still be read.
    """

    installation_id: str
    installation_proof_key_fingerprint: str
    binding: CurrentnessBinding


def decode_pin_facts(
    raw: bytes,
    *,
    expected: CurrentnessBinding,
    installation_id: str,
    installation_proof_key_fingerprint: str,
) -> PinComparisonFacts:
    try:
        if type(expected) is not CurrentnessBinding:
            raise PrivateFactsDenied()
        expected.__post_init__()
        if type(installation_id) is not str or type(installation_proof_key_fingerprint) is not str:
            raise PrivateFactsDenied()
        require_uuid(installation_id)
        require_digest(installation_proof_key_fingerprint)
        value = _read(raw, MAX_PIN_FACTS, 4)
        if (
            type(value) is not dict
            or set(value) != FIELDS
            or value["schema"] != PIN_FACTS_SCHEMA
            or value["installation_id"] != installation_id
            or value["installation_proof_key_fingerprint"] != installation_proof_key_fingerprint
            or raw != rfc8785.dumps(value)
        ):
            raise PrivateFactsDenied()
        pin = value["pin"]
        if type(pin) is not dict or set(pin) != HEAD_FIELDS:
            raise PrivateFactsDenied()
        scopes = value["affected_scopes"]
        if type(scopes) is not list or not 0 < len(scopes) <= 4096:
            raise PrivateFactsDenied()
        tuples = []
        for scope in scopes:
            if type(scope) is not dict or set(scope) != set(SCOPE_FIELDS):
                raise PrivateFactsDenied()
            tuples.append(tuple(scope[name] for name in SCOPE_FIELDS))
        text = value["root_public_key"]
        if type(text) is not str or len(text) != 43:
            raise PrivateFactsDenied()
        public = base64.b64decode(text + "=", altchars=b"-_", validate=True)
        if base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii") != text:
            raise PrivateFactsDenied()
        binding = CurrentnessBinding(
            journal=expected.journal,
            installed_pin=JournalHead(**pin),
            designation_id=value["designation_id"],
            designation_record_digest=value["designation_record_digest"],
            deployment_owner_ref=value["deployment_owner_ref"],
            affected_scopes=tuple(tuples),
            root_key_id=value["root_key_id"],
            root_fingerprint=value["root_fingerprint"],
            root_public_key=public,
            status=value["status"],
            domain=value["domain"],
        )
        if binding != expected or installation_id not in {scope[0] for scope in tuples}:
            raise PrivateFactsDenied()
        return PinComparisonFacts(installation_id, installation_proof_key_fingerprint, binding)
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, WitnessLifetimeDenied):
        raise PrivateFactsDenied() from None
