"""Private offline-pinned registration originals; no runtime enrollment or issuer."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import rfc8785

from backend.bootstrap_authority.ibla.contracts import IblaDenied, IblaInconsistent
from backend.bootstrap_authority.ibla.registration_codec import (
    REGISTRATION_FIELDS,
    SCOPE_DOMAIN,
    canonical,
    signed,
)
from backend.bootstrap_authority.ibla.source_codec import comparison, original
from backend.bootstrap_authority.ibla.source_reader import _Role
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.source_custody import _CustodyDesignationRecordFiles


class _IntentFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-registration-intent-v1.json"


class _RegistrationConfirmationFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-registration-confirmation-v1.json"


class _RegistrationOriginalFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-registration-original-v1.txt"


class _RegistrationDelegationFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-registration-delegation-v1.txt"


READERS = (
    _IntentFiles,
    _RegistrationConfirmationFiles,
    _RegistrationOriginalFiles,
    _RegistrationDelegationFiles,
)
ROLES = (
    "registration-intent",
    "registration-confirmation",
    "registration-original",
    "registration-delegation",
)


@dataclass(frozen=True, slots=True, repr=False)
class _RegistrationOriginals:
    accepted_intent: bytes
    accepted_confirmation: bytes
    original_ref: str
    original_digest: str
    delegation_digest: str
    delegation_start: datetime
    delegation_end: datetime
    writer_ref: str
    initializer_ref: str
    root_key_id: str
    initializer_key_id: str
    roles: tuple[_Role, ...]

    def __repr__(self):
        return "<IBLA registration originals>"


class _HeldRegistration:
    def __init__(self, setup, source):
        if type(setup) is not _RegistrationOriginals:
            raise IblaDenied()
        self.setup, self.source = setup, source
        self.files, self.raw = [], []
        if type(setup.roles) is not tuple or len(setup.roles) != 4:
            raise IblaDenied()
        for role, name, reader_type in zip(setup.roles, ROLES, READERS, strict=True):
            if type(role) is not _Role or role.role != name:
                raise IblaDenied()
            reader = reader_type(role.root, role.policy)
            self.files.append(reader)
            self.raw.append(source.stack.enter_context(reader._snapshot()))
        self.validate()

    def __repr__(self):
        return "<held IBLA registration originals>"

    def validate(self):
        try:
            for files, raw in zip(self.files, self.raw, strict=True):
                files._require_same_bytes(digest(raw))
            s, source, now = self.setup, self.source, datetime.now(UTC)
            if (
                type(s.delegation_start) is not datetime
                or type(s.delegation_end) is not datetime
                or s.delegation_start.tzinfo != UTC
                or s.delegation_end.tzinfo != UTC
                or not s.delegation_start <= now < s.delegation_end
            ):
                raise IblaDenied()
            if (
                original(self.raw[2]) != s.original_digest
                or original(self.raw[3]) != s.delegation_digest
            ):
                raise IblaInconsistent()
            a, c, binding, _, cd = source._correlate(now)
            r, rd, re = signed(
                self.raw[0],
                confirmation=False,
                public=source.setup.root_public,
                fingerprint=a["root_fingerprint"],
                checked_at=now,
            )
            q, qd, qe = signed(
                self.raw[1],
                confirmation=True,
                public=source.setup.initializer_public,
                fingerprint=a["initializer_fingerprint"],
                checked_at=now,
            )
            if rfc8785.dumps(r) != s.accepted_intent or rfc8785.dumps(q) != s.accepted_confirmation:
                raise IblaInconsistent()
            exact = dict(
                binding=asdict(binding),
                inventory_digest=a["inventory_digest"],
                registration_scope_digest=comparison(SCOPE_DOMAIN, a["inventory"]["scopes"]),
                intended_journal_id=a["journal_id"],
                writer_ref=a["ledger_custodian_ref"],
                initializer_ref=a["initializer_ref"],
                root_key_id=a["root_key_id"],
                initializer_key_id=a["initializer_key_id"],
                positive_origin_digest=a["positive_origin_digest"],
                commissioning_confirmation_digest=cd,
            )
            if any(r[k] != v for k, v in exact.items()):
                raise IblaInconsistent()
            for k in ("writer_ref", "initializer_ref", "root_key_id", "initializer_key_id"):
                if getattr(s, k) != r[k]:
                    raise IblaDenied()
            if (
                q["intent_digest"] != rd
                or q["initializer_ref"] != r["initializer_ref"]
                or q["initializer_key_id"] != r["initializer_key_id"]
                or q["original_confirmation_ref"] != s.original_ref
                or q["original_confirmation_digest"] != s.original_digest
                or q["original_confirmation_digest"] == c["original_confirmation_digest"]
                or q["issued_at"] < r["issued_at"]
                or qe > re
            ):
                raise IblaInconsistent()
            self.intent, self.intent_digest, self.confirmation_digest = r, rd, qd
            return r, rd, qd
        except IblaDenied:
            raise
        except Exception:
            raise IblaInconsistent() from None

    def event(self, observation_id):
        r, rd, qd = self.validate()
        nested = {k: r[k] for k in REGISTRATION_FIELDS if k in r}
        nested.update(intent_digest=rd, confirmation_digest=qd, observation_id=observation_id)
        wire = rfc8785.dumps(
            dict(
                schema="dohamusic/ibla-ledger-event/v2",
                binding=r["binding"],
                event_id=r["registration_id"],
                operation_id=r["operation_id"],
                revision=2,
                previous_digest=r["expected_l_head"]["digest"],
                kind="REGISTRATION_COMMITTED",
                evidence_digest=rd,
                recorded_at=r["recorded_at"],
                registration=nested,
            )
        )
        canonical(wire)
        return wire
