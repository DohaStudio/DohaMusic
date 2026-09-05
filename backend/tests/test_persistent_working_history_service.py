"""Backend-authoritative persistent WorkingComposition history tests."""

from decimal import Decimal

import pytest

from backend.models.workspace import CompositionClip, WorkingComposition
from backend.services.workspace import WorkingCompositionError, WorkingCompositionErrorCode
from backend.tests.test_working_composition_service import (
    _create_clip,
    _create_track,
    _initialize,
    graph,
    schema_template,
    service,
    session_factory,
)

__all__ = ["graph", "schema_template", "service", "session_factory"]


def test_gain_fade_history_is_persistent_strict_lifo_and_idempotent(
    service, session_factory, graph
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    track_id = _create_track(service, graph, working_id, 0).identities["track_id"]
    clip_id = _create_clip(service, graph, working_id, track_id, 1).identities["clip_id"]

    empty = service.get_history_state(
        graph.project_id,
        working_composition_id=working_id,
        effective_owner_id=graph.owner_id,
    )
    assert (empty["cursor"], empty["command_count"], empty["can_undo"]) == (0, 0, False)

    service.set_clip_gain(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        gain_db=Decimal("3.00"),
        expected_revision=2,
        effective_owner_id=graph.owner_id,
        idempotency_key="history-gain",
    )
    service.set_clip_fade(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        fade_in=Decimal("0.25"),
        fade_out=Decimal("0.5"),
        expected_revision=3,
        effective_owner_id=graph.owner_id,
        idempotency_key="history-fade",
    )
    undone = service.undo_history(
        graph.project_id,
        working_composition_id=working_id,
        expected_revision=4,
        effective_owner_id=graph.owner_id,
        idempotency_key="history-undo-fade",
    )
    replay = service.undo_history(
        graph.project_id,
        working_composition_id=working_id,
        expected_revision=4,
        effective_owner_id=graph.owner_id,
        idempotency_key="history-undo-fade",
    )
    assert undone.completed_revision == replay.completed_revision == 5
    assert replay.replayed is True
    with session_factory() as session:
        clip = session.get(CompositionClip, clip_id)
        assert (clip.gain_db, clip.fade_in, clip.fade_out) == (Decimal("3.00"), 0, 0)
        assert session.get(WorkingComposition, working_id).revision == 5

    redone = service.redo_history(
        graph.project_id,
        working_composition_id=working_id,
        expected_revision=5,
        effective_owner_id=graph.owner_id,
        idempotency_key="history-redo-fade",
    )
    assert redone.completed_revision == 6
    with session_factory() as session:
        clip = session.get(CompositionClip, clip_id)
        assert (clip.fade_in, clip.fade_out) == (250_000, 500_000)


def test_new_forward_command_invalidates_redo_and_empty_history_is_atomic(
    service, session_factory, graph
) -> None:
    working_id = _initialize(service, graph).identities["working_composition_id"]
    track_id = _create_track(service, graph, working_id, 0).identities["track_id"]
    clip_id = _create_clip(service, graph, working_id, track_id, 1).identities["clip_id"]
    service.set_clip_gain(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        gain_db=Decimal("1.00"),
        expected_revision=2,
        effective_owner_id=graph.owner_id,
        idempotency_key="branch-gain",
    )
    service.undo_history(
        graph.project_id,
        working_composition_id=working_id,
        expected_revision=3,
        effective_owner_id=graph.owner_id,
        idempotency_key="branch-undo",
    )
    service.set_clip_gain(
        graph.project_id,
        working_composition_id=working_id,
        clip_id=clip_id,
        gain_db=Decimal("2.00"),
        expected_revision=4,
        effective_owner_id=graph.owner_id,
        idempotency_key="branch-replacement",
    )
    state = service.get_history_state(
        graph.project_id,
        working_composition_id=working_id,
        effective_owner_id=graph.owner_id,
    )
    assert (state["cursor"], state["command_count"], state["can_redo"]) == (1, 1, False)
    service.undo_history(
        graph.project_id,
        working_composition_id=working_id,
        expected_revision=5,
        effective_owner_id=graph.owner_id,
        idempotency_key="branch-final-undo",
    )
    with pytest.raises(WorkingCompositionError) as caught:
        service.undo_history(
            graph.project_id,
            working_composition_id=working_id,
            expected_revision=6,
            effective_owner_id=graph.owner_id,
            idempotency_key="empty-undo",
        )
    assert caught.value.code is WorkingCompositionErrorCode.WORKING_HISTORY_EMPTY
    with session_factory() as session:
        assert session.get(WorkingComposition, working_id).revision == 6
