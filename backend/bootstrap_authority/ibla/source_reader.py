"""Internal offline-composed authentic source; never selected by requests/env.

No production initializer is supplied. Disposable tests independently provision
accepted originals, delegation/pins, mapping and native policies before opening.
These comparison inputs are not a public authentication or enrollment API.
"""

import ntpath
import os
import sqlite3
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import get_native_id

import rfc8785
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.bootstrap_authority.ibla.checkpoint import CheckpointRepository
from backend.bootstrap_authority.ibla.contracts import (
    Binding,
    IblaConflict,
    IblaDenied,
    IblaInconsistent,
)
from backend.bootstrap_authority.ibla.repository import LedgerRepository, database_path
from backend.bootstrap_authority.ibla.source_codec import (
    ARRAY_FIELDS,
    CUSTODY_DOMAIN,
    INVENTORY_DOMAIN,
    MAPPING_DOMAIN,
    MAPPING_FIELDS,
    comparison,
    inventory,
    original,
    signed,
)
from backend.bootstrap_authority.ibla.source_native import (
    _AnchorFiles,
    _CeremonyFiles,
    _CheckpointFiles,
    _ConfirmationFiles,
    _DatabaseFiles,
    _DesignationFiles,
    _MappingFiles,
)
from backend.bootstrap_authority.lifecycle_verifier import _read, digest
from backend.bootstrap_authority.provisioning_binding import _machine
from backend.bootstrap_authority.source_custody import SourceCustodyPolicy

ROLES = ("anchor", "confirmation", "designation", "ceremony", "mapping", "ledger", "checkpoint")
READERS = (
    _AnchorFiles,
    _ConfirmationFiles,
    _DesignationFiles,
    _CeremonyFiles,
    _MappingFiles,
    _DatabaseFiles,
    _CheckpointFiles,
)


@dataclass(frozen=True, slots=True, repr=False)
class _Role:
    role: str
    root: str
    logical_id: str
    policy: SourceCustodyPolicy


@dataclass(frozen=True, slots=True, repr=False)
class _CommissionedSource:
    """Private trusted-composition boundary, NOT a runtime caller input DTO.

    accepted A/C payloads and original digests are independently retained results
    of the original governance/initializer action. Never adopt discovered values.
    No public constructor/factory/wiring to runtime configuration exists.
    """

    accepted_anchor: bytes
    accepted_confirmation: bytes
    root_public: bytes
    initializer_public: bytes
    proof_public: bytes
    designation_digest: str
    ceremony_digest: str
    retained_mapping: bytes
    roles: tuple[_Role, ...]


def custody_digest(roles, identities):
    if type(roles) is not tuple or len(roles) != len(ROLES):
        raise IblaDenied()
    rows = []
    for role, name in zip(roles, ROLES, strict=True):
        if (
            type(role) is not _Role
            or role.role != name
            or type(role.policy) is not SourceCustodyPolicy
        ):
            raise IblaDenied()
        role.policy.__post_init__()
        rows.append({"role": name, "logical_id": role.logical_id, "policy": _machine(role.policy)})
    return comparison(CUSTODY_DOMAIN, {"identities": identities, "roles": rows})


def custody_identities(a):
    return {
        key: a[key]
        for key in (
            "domain_id",
            "deployment_id",
            "installation_id",
            "installation_proof_digest",
            "lineage_id",
            "journal_id",
            "authority_epoch",
        )
    }


class _HeldSource:
    def __init__(self, commissioned):
        if type(commissioned) is not _CommissionedSource:
            raise IblaDenied()
        self.setup = commissioned
        self.stack = ExitStack()
        self.files, self.raw, self.engines, self.connections = [], [], [], []
        self.anchor = self.confirmation = self.binding = self.tuple = None
        self.expiry = None
        self.closed = False
        self.owner = (os.getpid(), get_native_id())

    def require_live(self):
        if self.closed or self.owner != (os.getpid(), get_native_id()):
            raise IblaDenied()
        for reader, raw in zip(self.files[:5], self.raw, strict=True):
            reader._require_same_bytes(digest(raw))
        for reader in self.files[5:]:
            reader.require_unchanged()
        # Outside a read pass, owners must be alive and have ended their transactions.
        for connection in self.connections:
            if connection.in_transaction:
                raise IblaDenied()

    def _engine(self, files):
        uri = "file:/" + files._journal_path.replace("\\", "/") + "?mode=ro"

        def connect():
            files.require_unchanged()
            connection = sqlite3.connect(uri, uri=True, timeout=0, check_same_thread=True)
            try:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("PRAGMA synchronous=EXTRA")
                files.require_unchanged()
                self.connections.append(connection)
                return connection
            except Exception:
                connection.close()
                raise

        engine = create_engine("sqlite+pysqlite://", creator=connect, poolclass=StaticPool)
        self.engines.append(engine)
        return engine

    def open(self, *, originals_only=False):
        setup = self.setup
        custody_digest(setup.roles, custody_identities(_read(setup.accepted_anchor, 1_048_576, 8)))
        for role, reader_type in zip(setup.roles, READERS, strict=True):
            reader = reader_type(role.root, role.policy)
            self.files.append(reader)
            if role.role in {"ledger", "checkpoint"}:
                self.stack.enter_context(reader.hold())
                self._engine(reader)
            else:
                self.raw.append(self.stack.enter_context(reader._snapshot()))
        if not originals_only:
            return self.read(datetime.now(UTC))

    def _correlate(self, checked):
        s = self.setup
        a, ad, ae = signed(
            self.raw[0],
            confirmation=False,
            public=s.root_public,
            fingerprint=digest(s.root_public),
            checked_at=checked,
        )
        c, cd, ce = signed(
            self.raw[1],
            confirmation=True,
            public=s.initializer_public,
            fingerprint=digest(s.initializer_public),
            checked_at=checked,
        )
        # Offline retained exact action/delegation/complete inventory, never self-discovered.
        if rfc8785.dumps(a) != s.accepted_anchor or rfc8785.dumps(c) != s.accepted_confirmation:
            raise IblaInconsistent()
        designation, ceremony = original(self.raw[2]), original(self.raw[3])
        if designation != s.designation_digest or ceremony != s.ceremony_digest:
            raise IblaInconsistent()
        if (
            a["designation_digest"] != designation
            or c["original_confirmation_digest"] != ceremony
            or a["root_fingerprint"] != digest(s.root_public)
            or a["initializer_fingerprint"] != digest(s.initializer_public)
            or a["installation_proof_digest"] != digest(s.proof_public)
        ):
            raise IblaInconsistent()
        for key in (
            "commissioning_action_id",
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
        ):
            if a[key] != c[key]:
                raise IblaInconsistent()
        if c["anchor_digest"] != ad:
            raise IblaInconsistent()
        i = a["inventory"]
        scopes = inventory(i)
        for key in (
            "domain_id",
            "deployment_id",
            "lineage_id",
            "installation_id",
            "installation_proof_digest",
            "journal_id",
            "positive_origin_ref",
            "positive_origin_digest",
        ):
            if i[key] != a[key]:
                raise IblaInconsistent()
        if any(scope[0] != a["installation_id"] for scope in scopes):
            raise IblaInconsistent()
        if comparison(INVENTORY_DOMAIN, i) != a["inventory_digest"]:
            raise IblaInconsistent()
        mapping = {key: a[key] for key in MAPPING_FIELDS}
        retained = _read(self.raw[4], 16_384, 4)
        if self.raw[4] != s.retained_mapping:
            raise IblaInconsistent()
        if s.retained_mapping != rfc8785.dumps(
            {"payload": mapping, "anchor_digest": ad}
        ) or retained != {"payload": mapping, "anchor_digest": ad}:
            raise IblaInconsistent()
        if comparison(MAPPING_DOMAIN, mapping) != a["commissioning_mapping_digest"]:
            raise IblaInconsistent()
        if custody_digest(s.roles, custody_identities(a)) != a["custody_provisioning_digest"]:
            raise IblaInconsistent()
        expected_ids = (
            a["anchor_id"],
            c["confirmation_id"],
            a["designation_id"],
            a["commissioning_action_id"],
            a["domain_id"],
            a["ledger_id"],
            a["checkpoint_id"],
        )
        if tuple(role.logical_id for role in s.roles) != expected_ids:
            raise IblaInconsistent()
        left, right = s.roles[-2:]
        lr, rr = ntpath.normcase(left.root), ntpath.normcase(right.root)
        if (
            left.policy.record_identity == right.policy.record_identity
            or left.policy.root_identity == right.policy.root_identity
            or lr == rr
            or lr.startswith(rr + "\\")
            or rr.startswith(lr + "\\")
        ):
            raise IblaInconsistent()
        # Unsupported transitions are retained/validated first, never erased to prove absence.
        known_prior = {
            "REGISTRATION_COMMITTED",
            "INITIAL_AUTHORIZATION_ISSUED",
            "INITIAL_AUTHORIZATION_CONSUMED",
            "INITIAL_AUTHORIZATION_CANCELLED",
            "GENESIS",
            "HISTORY_BLOCK",
            "RETIRE",
        }
        if any(row["fact_kind"] in known_prior for row in i["external_history"]):
            raise IblaConflict()
        if any(i[key] for key in ARRAY_FIELDS):
            raise IblaDenied()
        binding = Binding(
            **{
                key: ad if key == "anchor_digest" else a[key]
                for key in Binding.__dataclass_fields__
            }
        )
        binding.validate()
        return a, c, binding, min(ae, ce), cd

    def read(self, checked):
        self.require_live()
        a, c, binding, expiry, cd = self._correlate(checked)
        with (
            Session(self.engines[0]) as ls,
            Session(self.engines[1]) as hs,
            ls.begin(),
            hs.begin(),
        ):
            for session, files in zip((ls, hs), self.files[5:], strict=True):
                session.execute(text("BEGIN"))
                if session.execute(text("PRAGMA query_only")).scalar_one() != 1 or ntpath.normcase(
                    database_path(session)
                ) != ntpath.normcase(files._journal_path):
                    raise IblaDenied()
            versions = [
                s.execute(text("SELECT version FROM ibla_identity")).scalar_one() for s in (ls, hs)
            ]
            if versions[0] != versions[1] or versions[0] not in {1, 2}:
                raise IblaDenied()
            ledger = LedgerRepository(ls, binding, version=versions[0])
            h = CheckpointRepository(
                hs,
                binding,
                ledger_reader=ledger,
                recorded_at=checked.strftime("%Y-%m-%dT%H:%M:%SZ"),
                version=versions[0],
            )
            try:
                lv = h._ledger()
            except IblaInconsistent:
                # Failure-only classification, no extra happy-path history scan.
                kinds = set(ls.execute(text("SELECT kind FROM ibla_events")).scalars())
                if kinds - {"COMMISSION", "HISTORY_BLOCK", "RETIRE"}:
                    raise IblaDenied() from None
                raise
            hv = h.read()
            h._require_confirmed(hv, lv)
            if len(lv.events) != 1:
                if any(e.kind == "REGISTRATION_COMMITTED" for e in lv.events):
                    raise IblaDenied()
                if any(e.kind in {"HISTORY_BLOCK", "RETIRE"} for e in lv.events):
                    raise IblaConflict()
                raise IblaInconsistent()
            event = _read(lv.events[0].envelope, 16_384, 4)
            if (
                lv.events[0].kind != "COMMISSION"
                or event["evidence_digest"] != binding.anchor_digest
            ):
                raise IblaInconsistent()
            ledger._check()
            h._check()
            snapshot = (
                binding,
                lv.head,
                hv,
                cd,
                a["inventory_digest"],
                a["commissioning_mapping_digest"],
                a["custody_provisioning_digest"],
                tuple(id(conn) for conn in self.connections),
            )
        # Normal known owner transaction closure; repositories do not escape this pass.
        for reader in self.files[5:]:
            reader.require_unchanged()
        if self.tuple is not None and self.tuple != snapshot:
            raise IblaInconsistent()
        self.anchor, self.confirmation, self.binding, self.expiry = a, c, binding, expiry
        self.tuple = snapshot
        return snapshot

    def close(self):
        if self.owner != (os.getpid(), get_native_id()):
            raise IblaDenied()
        self.closed = True
        for engine in reversed(self.engines):
            engine.dispose()
        self.stack.close()
