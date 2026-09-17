from __future__ import annotations

from math import inf, nan
from uuid import uuid4

import pytest

from backend.contracts.music_director_proposal import (
    MAX_PROPOSAL_OPERATIONS,
    MusicDirectorProposalError,
    MusicDirectorProposalErrorCode,
    validate_music_director_proposal,
)
from backend.tests.test_music_director_candidate_persistence_service import Graph


def _payload(snapshot_id, operations):
    return {
        "schema_version": 1,
        "source_snapshot_id": str(snapshot_id),
        "operations": operations,
    }


def test_proposal_is_canonical_and_snapshot_bound(tmp_path) -> None:
    graph = Graph(tmp_path, count=1)
    payload = _payload(
        graph.request.composition_snapshot_id,
        [{"gain_db": 0.5, "operation": "set_master_gain"}],
    )
    with graph.factory() as session:
        first = validate_music_director_proposal(session, payload)
        second = validate_music_director_proposal(session, payload)

    assert first.source_snapshot_id == graph.request.composition_snapshot_id
    assert first.canonical_bytes == second.canonical_bytes
    assert first.digest == second.digest
    assert len(first.digest) == 64
    assert first.canonical_bytes.startswith(b'{"operations"')
    graph.engine.dispose()


@pytest.mark.parametrize(
    ("operations", "code"),
    [
        ([], MusicDirectorProposalErrorCode.INVALID_CARDINALITY),
        (
            [
                {"operation": "set_master_gain", "gain_db": 1},
                {"operation": "set_master_gain", "gain_db": 2},
            ],
            MusicDirectorProposalErrorCode.DUPLICATE_MUTATION,
        ),
        (
            [{"operation": "unknown", "gain_db": 0}],
            MusicDirectorProposalErrorCode.INVALID_OPERATION,
        ),
        (
            [{"operation": "set_master_gain", "gain_db": 24.01}],
            MusicDirectorProposalErrorCode.INVALID_VALUE,
        ),
    ],
)
def test_proposal_rejects_invalid_structure(tmp_path, operations, code) -> None:
    graph = Graph(tmp_path, count=1)
    with graph.factory() as session, pytest.raises(MusicDirectorProposalError) as error:
        validate_music_director_proposal(
            session, _payload(graph.request.composition_snapshot_id, operations)
        )
    assert error.value.code is code
    graph.engine.dispose()


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_proposal_rejects_non_finite_values(tmp_path, value) -> None:
    graph = Graph(tmp_path, count=1)
    with graph.factory() as session, pytest.raises(MusicDirectorProposalError) as error:
        validate_music_director_proposal(
            session,
            _payload(
                graph.request.composition_snapshot_id,
                [{"operation": "set_master_gain", "gain_db": value}],
            ),
        )
    assert error.value.code is MusicDirectorProposalErrorCode.INVALID_VALUE
    graph.engine.dispose()


def test_proposal_rejects_unknown_snapshot_target(tmp_path) -> None:
    graph = Graph(tmp_path, count=1)
    with graph.factory() as session, pytest.raises(MusicDirectorProposalError) as error:
        validate_music_director_proposal(
            session,
            _payload(
                graph.request.composition_snapshot_id,
                [
                    {
                        "operation": "set_track_gain",
                        "canonical_track_id": str(uuid4()),
                        "gain_db": 0,
                    }
                ],
            ),
        )
    assert error.value.code is MusicDirectorProposalErrorCode.INVALID_TARGET
    graph.engine.dispose()


def test_proposal_operation_count_is_bounded(tmp_path) -> None:
    graph = Graph(tmp_path, count=1)
    operations = [
        {
            "operation": "set_clip_gain",
            "clip_id": str(uuid4()),
            "gain_db": 0,
        }
        for _ in range(MAX_PROPOSAL_OPERATIONS + 1)
    ]
    with graph.factory() as session, pytest.raises(MusicDirectorProposalError) as error:
        validate_music_director_proposal(
            session, _payload(graph.request.composition_snapshot_id, operations)
        )
    assert error.value.code is MusicDirectorProposalErrorCode.INVALID_CARDINALITY
    graph.engine.dispose()
