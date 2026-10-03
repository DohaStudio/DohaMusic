"""ADR-110 PRE-only read-only verifier and ephemeral first-registration handoff.

Production remains unavailable. There is no registration/IA/GENESIS writer,
HTTP wiring, source enrollment, serializer, fallback or persistent token.
"""

import base64
import math
import os
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock, get_native_id
from uuid import uuid4

import rfc8785

from backend.bootstrap_authority.ibla.contracts import IblaConflict, IblaDenied, IblaInconsistent
from backend.bootstrap_authority.ibla.source_codec import POSSESSION_DOMAIN, verify_signature
from backend.bootstrap_authority.ibla.source_native import _DomainLease
from backend.bootstrap_authority.ibla.source_reader import _CommissionedSource, _HeldSource
from backend.bootstrap_authority.lifecycle_verifier import _read

_MINT = object()


class _Opaque:
    __slots__ = ()

    def __new__(cls, mint=None):
        if mint is not _MINT:
            raise IblaDenied()
        return super().__new__(cls)

    def __init_subclass__(cls, **kwargs):
        raise TypeError("OPAQUE_IBLA_HANDLE")

    def __copy__(self):
        raise TypeError("OPAQUE_IBLA_HANDLE")

    def __deepcopy__(self, memo):
        raise TypeError("OPAQUE_IBLA_HANDLE")

    def __reduce_ex__(self, protocol):
        raise TypeError("OPAQUE_IBLA_HANDLE")

    def __repr__(self):
        return "<opaque IBLA handle>"


@dataclass(slots=True, repr=False)
class _Observation:
    context: _Opaque
    source: _HeldSource
    lease: _DomainLease
    owner: tuple[int, int]
    attempt: object
    message: bytes
    started: float
    deadline: float
    last_mono: float
    last_wall: datetime
    verified: _Opaque | None = None
    capability: _Opaque | None = None
    invalid: bool = False
    proof_used: bool = False
    delivered: bool = False
    delivering: bool = False


class UnavailableIblaSourceVerifier:
    """Only production port: no source/env/request enrollment or fixture fallback."""

    def open_verified_source(self, *args, **kwargs):
        raise IblaDenied()


class _IblaSourceVerifier:
    """Private reviewed composition and test consumer only; no runtime factory.

    Caller-created public comparison facts cannot enter this provider's registries.
    Native custody, retained originals/delegation, independently pinned signatures,
    complete coverage/current H and fresh possession all precede capability mint.
    """

    def __init__(self, commissioned, *, consumer):
        if type(commissioned) is not _CommissionedSource or not callable(consumer):
            raise IblaDenied()
        self._setup, self._consumer = commissioned, consumer
        self._lock, self._records, self._retained = RLock(), {}, []
        self._shutdown = False

    def __repr__(self):
        return "<IBLA source verifier>"

    def _lookup(self, handle, field):
        if type(handle) is not _Opaque:
            raise IblaDenied()
        record = self._records.get(id(handle))
        if record is None or getattr(record, field) is not handle:
            raise IblaDenied()
        return record

    def _live(self, record, *, read=True):
        if record.invalid or self._shutdown:
            raise IblaDenied()
        if record.owner != (os.getpid(), get_native_id()):
            # A foreign attempted use cannot destroy an original owner's live attempt.
            raise IblaDenied()
        try:
            mono, wall = time.monotonic(), datetime.now(UTC)
            if (
                not math.isfinite(mono)
                or mono < record.last_mono
                or wall < record.last_wall
                or mono >= record.deadline
                or wall >= record.source.expiry
            ):
                raise IblaDenied()
            record.lease.require_live()
            if read:
                record.source.read(wall)
            else:
                record.source.require_live()
            record.last_mono, record.last_wall = mono, wall
        except IblaDenied:
            record.invalid = True
            raise
        except Exception:
            record.invalid = True
            raise IblaDenied() from None

    @contextmanager
    def observe(self):
        """Hold original source/lease; nonce is provider-owned, never caller selected."""
        with self._lock:
            if self._shutdown or self._retained:
                raise IblaDenied()
        source, lease, record = _HeldSource(self._setup), None, None
        try:
            expected = _read(self._setup.accepted_anchor, 1_048_576, 8)
            lease = _DomainLease(expected["domain_id"])
            self._retained.append((source, lease))
            with lease.hold():
                source.open()
                mono, wall = time.monotonic(), datetime.now(UTC)
                if not math.isfinite(mono) or source.expiry <= wall:
                    raise IblaDenied()
                p = source.anchor
                message = POSSESSION_DOMAIN + rfc8785.dumps(
                    {
                        "domain_id": p["domain_id"],
                        "anchor_digest": source.binding.anchor_digest,
                        "installation_id": p["installation_id"],
                        "installation_proof_digest": p["installation_proof_digest"],
                        "lineage_id": p["lineage_id"],
                        "inventory_digest": p["inventory_digest"],
                        "observation_id": str(uuid4()),
                        "challenge": base64.urlsafe_b64encode(secrets.token_bytes(32))
                        .rstrip(b"=")
                        .decode(),
                    }
                )
                context = _Opaque(_MINT)
                record = _Observation(
                    context,
                    source,
                    lease,
                    (os.getpid(), get_native_id()),
                    object(),
                    message,
                    mono,
                    mono + min(900, (source.expiry - wall).total_seconds()),
                    mono,
                    wall,
                )
                with self._lock:
                    self._records[id(context)] = record
                try:
                    yield context
                    self._live(record, read=False)
                finally:
                    record.invalid = True
                    # Close DB owners/held files while original domain lease is still owned.
                    source.close()
            self._retained.remove((source, lease))
        except IblaDenied:
            raise
        except Exception:
            raise IblaDenied() from None
        finally:
            if record is not None:
                record.invalid = True
                with self._lock:
                    for handle in (record.context, record.verified, record.capability):
                        if handle is not None:
                            self._records.pop(id(handle), None)
            if not source.closed:
                try:
                    source.close()
                except Exception:
                    raise IblaDenied() from None

    def challenge(self, context):
        with self._lock:
            record = self._lookup(context, "context")
            self._live(record)
            if record.proof_used:
                raise IblaConflict()
            return record.message  # Public challenge only, never raw source or private custody.

    def verify_source(self, context, proof):
        with self._lock:
            record = self._lookup(context, "context")
            self._live(record)
            if record.proof_used:
                raise IblaConflict()
            record.proof_used = True
            try:
                verify_signature(
                    self._setup.proof_public,
                    record.source.binding.installation_proof_digest,
                    record.message,
                    proof,
                )
                self._live(record)
            except IblaDenied:
                record.invalid = True
                raise
            except Exception:
                record.invalid = True
                raise IblaInconsistent() from None
            record.verified = _Opaque(_MINT)
            self._records[id(record.verified)] = record
            return record.verified

    def mint(self, verified_source):
        with self._lock:
            record = self._lookup(verified_source, "verified")
            # Duplicate mint does not abandon a still-valid original winner.
            if record.capability is not None:
                raise IblaConflict()
            self._eligibility(record)
            record.capability = _Opaque(_MINT)
            self._records[id(record.capability)] = record
            return record.capability

    def _eligibility(self, record):
        self._live(record)
        # Facts originate only in the just-completed original held-source pass.
        snapshot = record.source.tuple
        inventory = record.source.anchor["inventory"]
        confirmed = snapshot[2]
        complete = not any(
            inventory[key]
            for key in (
                "installation_aliases",
                "lineage_aliases",
                "journal_aliases",
                "imported_scope_refs",
                "external_history",
            )
        )
        predicates = {
            "authentic_origin": record.proof_used and record.verified is not None,
            "exact_commissioned_domain": snapshot[0] == record.source.binding,
            "complete_supported_coverage": complete,
            "current_confirmed": confirmed.state == "CONFIRMED"
            and confirmed.pending is None
            and confirmed.confirmed == snapshot[1],
            "no_prior_registration": complete and snapshot[1].revision == 1,
            "no_prior_initial_authorization_or_genesis": complete and snapshot[1].revision == 1,
            "no_block_or_terminal": snapshot[1].revision == 1,
            "live_observation": not record.invalid,
        }
        if not all(predicates.values()):
            record.invalid = True
            raise IblaDenied()

    def require_handoff(self, capability):
        """Fixed consumer validates original registry identity during callback only."""
        with self._lock:
            record = self._lookup(capability, "capability")
            self._live(record, read=False)
            if not record.delivered or not record.delivering:
                raise IblaDenied()

    def handoff(self, capability):
        with self._lock:
            record = self._lookup(capability, "capability")
            if record.delivered:
                raise IblaConflict()
            self._eligibility(record)
            # All query-only read passes have ended before calling the consumer.
            record.delivered, record.delivering = True, True
            try:
                result = self._consumer(capability)
                self._live(record, read=False)
                return result
            except Exception:
                record.invalid = True
                raise IblaDenied() from None
            finally:
                record.delivering = False

    def close(self):
        with self._lock:
            self._shutdown = True
            for record in self._records.values():
                record.invalid = True
            # Native resource cleanup remains the original observation owner's duty.
