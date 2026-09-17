from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace import CompositionSnapshotClip, CompositionSnapshotTrack

MUSIC_DIRECTOR_PROPOSAL_SCHEMA_VERSION = 1
MAX_PROPOSAL_OPERATIONS = 641


class MusicDirectorProposalErrorCode(StrEnum):
    INVALID_SCHEMA = "INVALID_SCHEMA"
    INVALID_OPERATION = "INVALID_OPERATION"
    INVALID_TARGET = "INVALID_TARGET"
    INVALID_VALUE = "INVALID_VALUE"
    INVALID_CARDINALITY = "INVALID_CARDINALITY"
    DUPLICATE_MUTATION = "DUPLICATE_MUTATION"


class MusicDirectorProposalError(ValueError):
    def __init__(self, code: MusicDirectorProposalErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class CanonicalMusicDirectorProposal:
    source_snapshot_id: UUID
    operations: tuple[dict[str, Any], ...]
    canonical_bytes: bytes
    digest: str


def validate_music_director_proposal(
    session: Session, payload: object
) -> CanonicalMusicDirectorProposal:
    if type(payload) is not dict or set(payload) != {
        "schema_version",
        "source_snapshot_id",
        "operations",
    }:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_SCHEMA)
    if payload["schema_version"] != MUSIC_DIRECTOR_PROPOSAL_SCHEMA_VERSION:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_SCHEMA)
    try:
        snapshot_id = UUID(str(payload["source_snapshot_id"]))
    except (TypeError, ValueError, AttributeError):
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_TARGET) from None
    operations = payload["operations"]
    if type(operations) is not list or not 1 <= len(operations) <= MAX_PROPOSAL_OPERATIONS:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_CARDINALITY)
    track_ids = set(
        session.scalars(
            select(CompositionSnapshotTrack.canonical_track_id).where(
                CompositionSnapshotTrack.composition_snapshot_id == snapshot_id
            )
        )
    )
    clip_ids = set(
        session.scalars(
            select(CompositionSnapshotClip.canonical_clip_id).where(
                CompositionSnapshotClip.composition_snapshot_id == snapshot_id
            )
        )
    )
    canonical: list[dict[str, Any]] = []
    mutations: set[tuple[str, UUID | None]] = set()
    for raw in operations:
        operation, mutation = _validate_operation(raw, track_ids=track_ids, clip_ids=clip_ids)
        if mutation in mutations:
            raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.DUPLICATE_MUTATION)
        mutations.add(mutation)
        canonical.append(operation)
    document = {
        "operations": canonical,
        "schema_version": MUSIC_DIRECTOR_PROPOSAL_SCHEMA_VERSION,
        "source_snapshot_id": str(snapshot_id),
    }
    canonical_bytes = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return CanonicalMusicDirectorProposal(
        snapshot_id,
        tuple(canonical),
        canonical_bytes,
        hashlib.sha256(canonical_bytes).hexdigest(),
    )


def _validate_operation(
    raw: object, *, track_ids: set[UUID], clip_ids: set[UUID]
) -> tuple[dict[str, Any], tuple[str, UUID | None]]:
    if type(raw) is not dict or type(raw.get("operation")) is not str:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_OPERATION)
    operation = raw["operation"]
    if operation == "set_clip_gain":
        return _targeted(raw, operation, "canonical_clip_id", "gain_db", clip_ids, -24, 24)
    if operation == "set_track_gain":
        return _targeted(raw, operation, "canonical_track_id", "gain_db", track_ids, -24, 24)
    if operation == "set_track_pan":
        return _targeted(raw, operation, "canonical_track_id", "pan", track_ids, -1, 1)
    if operation == "set_master_gain":
        if set(raw) != {"operation", "gain_db"}:
            raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_OPERATION)
        return {
            "gain_db": _number(raw["gain_db"], -24, 24),
            "operation": operation,
        }, (operation, None)
    raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_OPERATION)


def _targeted(
    raw: dict[str, Any],
    operation: str,
    target_name: str,
    value_name: str,
    valid_targets: set[UUID],
    minimum: int,
    maximum: int,
) -> tuple[dict[str, Any], tuple[str, UUID]]:
    if set(raw) != {"operation", target_name, value_name}:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_OPERATION)
    try:
        target = UUID(str(raw[target_name]))
    except (TypeError, ValueError, AttributeError):
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_TARGET) from None
    if target not in valid_targets:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_TARGET)
    return {
        target_name: str(target),
        "operation": operation,
        value_name: _number(raw[value_name], minimum, maximum),
    }, (operation, target)


def _number(value: object, minimum: int, maximum: int) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_VALUE)
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_VALUE) from None
    if not number.is_finite() or number < minimum or number > maximum:
        raise MusicDirectorProposalError(MusicDirectorProposalErrorCode.INVALID_VALUE)
    return int(number) if number == number.to_integral_value() else float(number.normalize())
