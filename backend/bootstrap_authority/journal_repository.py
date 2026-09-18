"""Flush-only independent public-fact repository; not an admission/runtime adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass

import rfc8785
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.bootstrap_authority.contracts import require_uuid
from backend.bootstrap_authority.lifecycle_verifier import (
    LifecycleExpectations,
    LifecycleIntegrityReceipt,
    digest,
    verify_lifecycle_integrity,
)


@dataclass(frozen=True, slots=True)
class JournalHead:
    journal_id: str
    revision: int
    trust_revision: int
    head_digest: str | None
    current_key_id: str | None
    last_key_id: str | None


@dataclass(frozen=True, slots=True)
class PublicKeyHistory:
    key_id: str
    fingerprint: str
    status: str
    tainted: bool
    invalidated_at_revision: int | None


class JournalRepository:
    """Caller owns the independent-store Session/transaction and error rollback.

    Public expectations/rows are NOT independently verified governance or lease
    provenance. No production admission writer consumes this repository yet.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def initialize_public_identity(self, journal_id: str) -> None:
        """Explicit public fact initialization, never trusted genesis/provisioning."""
        require_uuid(journal_id)
        self.session.execute(
            text("INSERT INTO deployment_journal_guard(singleton,journal_id) VALUES(1,:id)"),
            {"id": journal_id},
        )
        self.session.flush()

    def read_public_head(self) -> JournalHead:
        row = self.session.execute(
            text(
                "SELECT journal_id,revision,trust_revision,head_digest,current_key_id,last_key_id "
                "FROM deployment_journal_guard WHERE singleton=1"
            )
        ).one_or_none()
        if row is None:
            raise RuntimeError("JOURNAL_UNAVAILABLE")
        return JournalHead(*row)

    def append_public_event(
        self,
        artifact: bytes,
        manifest: bytes,
        *,
        expected: LifecycleExpectations,
    ) -> LifecycleIntegrityReceipt:
        receipt = verify_lifecycle_integrity(artifact, manifest, expected=expected)
        p = json.loads(receipt.canonical_envelope)["payload"]
        # The INSERT trigger atomically executes the actual conditional guard UPDATE.
        # Ledger, monotonic head and nullable current pointer are one SQL statement.
        self.session.execute(
            text(
                "INSERT INTO deployment_journal_events VALUES "
                "(:event,:journal,:revision,:previous,:digest,:kind,:old,:old_fp,:new,:new_fp,:wire)"
            ),
            {
                "event": p["event_id"],
                "journal": p["journal_id"],
                "revision": p["revision"],
                "previous": p["previous_event_digest"],
                "digest": receipt.event_digest,
                "kind": p["event_kind"],
                "old": p["old_key_id"],
                "old_fp": p["old_key_fingerprint"],
                "new": p["new_key_id"],
                "new_fp": p["new_key_fingerprint"],
                "wire": receipt.canonical_envelope,
            },
        )
        self.session.flush()
        return receipt

    def read_public_history(self) -> tuple[PublicKeyHistory, ...]:
        """Check local hash/order/projection consistency, NOT external currentness.

        Historical terminal state remains unchanged; redesignation appends a taint
        observation for its predecessor. Additional independently designated historical
        taint targets require the future admission adapter, not a caller-supplied list.
        """
        head = self.read_public_head()
        rows = self.session.execute(
            text(
                "SELECT revision,previous_digest,event_digest,kind,old_key_id,old_fingerprint,"
                "new_key_id,new_fingerprint,envelope,event_id,journal_id "
                "FROM deployment_journal_events ORDER BY revision"
            )
        ).all()
        previous = None
        current = last = None
        history = {}
        try:
            for revision, row in enumerate(rows, 1):
                wire = row.envelope
                envelope = json.loads(wire)
                p = envelope["payload"]
                if (
                    row.revision != revision
                    or row.previous_digest != previous
                    or row.journal_id != head.journal_id
                    or digest(wire) != row.event_digest
                    or rfc8785.dumps(envelope) != wire
                ):
                    raise ValueError("LINEAGE")
                for column, field in (
                    ("revision", "revision"),
                    ("previous_digest", "previous_event_digest"),
                    ("kind", "event_kind"),
                    ("old_key_id", "old_key_id"),
                    ("old_fingerprint", "old_key_fingerprint"),
                    ("new_key_id", "new_key_id"),
                    ("new_fingerprint", "new_key_fingerprint"),
                    ("event_id", "event_id"),
                    ("journal_id", "journal_id"),
                ):
                    if getattr(row, column) != p[field]:
                        raise ValueError("PROJECTION")
                if row.old_key_id:
                    old = history[row.old_key_id]
                    status = old.status
                    if status == "ACTIVE_ISSUANCE":
                        status = {
                            "NORMAL_ROTATION": "RETIRED",
                            "REVOKE": "REVOKED",
                            "EXTERNAL_REDESIGNATION": "COMPROMISED",
                        }[row.kind]
                    history[old.key_id] = PublicKeyHistory(
                        old.key_id,
                        old.fingerprint,
                        status,
                        old.tainted or row.kind == "EXTERNAL_REDESIGNATION",
                        old.invalidated_at_revision or revision,
                    )
                if row.new_key_id:
                    history[row.new_key_id] = PublicKeyHistory(
                        row.new_key_id,
                        row.new_fingerprint,
                        "ACTIVE_ISSUANCE",
                        False,
                        None,
                    )
                current = row.new_key_id
                last = row.new_key_id or last
                previous = row.event_digest
            if (
                len(rows) != head.revision
                or head.trust_revision != head.revision
                or previous != head.head_digest
                or current != head.current_key_id
                or last != head.last_key_id
            ):
                raise ValueError("HEAD")
        except (ValueError, TypeError, KeyError, UnicodeError, rfc8785.CanonicalizationError):
            raise RuntimeError("JOURNAL_INCONSISTENT") from None
        return tuple(history.values())

    def require_public_pin_match(self, installed_public_head: JournalHead) -> None:
        """Mismatch check only; equality never supplies a private pin/lease witness."""
        self.read_public_history()
        if type(installed_public_head) is not JournalHead or (
            installed_public_head != self.read_public_head()
        ):
            raise RuntimeError("JOURNAL_PIN_MISMATCH")
