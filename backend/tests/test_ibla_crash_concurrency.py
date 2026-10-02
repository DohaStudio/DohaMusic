"""Deterministic process restart and Event/Barrier schedules, never sleep races."""

import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.bootstrap_authority.ibla.codec import parse_event
from backend.bootstrap_authority.ibla.contracts import Head, IblaDenied
from backend.tests.ibla_support import (
    BINDING,
    advance,
    candidate,
    keeper,
    ledger,
    process_read,
    process_stage,
    stores,
)


@pytest.mark.parametrize("stage", ["prepared", "appended", "confirmed"])
def test_abrupt_process_exit_restart_and_exact_reconciliation(tmp_path, stage):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    wire = candidate(Head(1, first.digest), number=101)
    target = parse_event(wire, BINDING)
    ctx = multiprocessing.get_context("spawn")
    process = ctx.Process(target=process_stage, args=(str(lp), str(hp), stage))
    process.start()
    process.join(30)
    assert not process.is_alive()
    assert process.exitcode == 0
    with keeper(lp, hp) as h:
        view = h.read()
        assert view.state == ("CONFIRMED" if stage == "confirmed" else "PREPARED")
        if stage != "confirmed":
            assert view.pending == wire
    with ledger(lp, readonly=True) as repo:
        assert repo.read().head.revision == (1 if stage == "prepared" else 2)
    if stage == "prepared":
        with keeper(lp, hp) as h, pytest.raises(IblaDenied):
            h.confirm(target.operation_id, target.fingerprint)
        with keeper(lp, hp) as h:
            h.mark_uncertain(target.operation_id, target.fingerprint)
        return
    with keeper(lp, hp) as h:
        result = h.confirm(target.operation_id, target.fingerprint)
        assert result.state == "CONFIRMED"
    with keeper(lp, hp) as h:
        assert h.confirm(target.operation_id, target.fingerprint) == result
    with ledger(lp, readonly=True) as repo:
        assert len(repo.read().events) == 2
    queue = ctx.Queue()
    process = ctx.Process(target=process_read, args=(str(lp), str(hp), queue))
    process.start()
    loaded = queue.get(timeout=30)
    process.join(30)
    assert process.exitcode == 0
    assert loaded["confirmed"] == {"revision": 2, "digest": target.digest}
    queue.close()
    queue.join_thread()


def concurrent(actions):
    barrier = Barrier(len(actions))

    def run(action):
        barrier.wait(timeout=10)
        try:
            return action()
        except (IblaDenied, SQLAlchemyError):
            # Owner's BEGIN IMMEDIATE contention is a conflict, not automatic retry.
            return "CONFLICT"

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures = [pool.submit(run, action) for action in actions]
        return [future.result(timeout=15) for future in futures]


def test_two_ledger_writers_same_head_one_winner(tmp_path):
    lp, _ = stores(tmp_path)

    def append(number):
        with ledger(lp) as repo:
            repo.append(candidate(number=number), expected=Head())
        return "WON"

    results = concurrent([lambda: append(100), lambda: append(101)])
    assert sorted(results) == ["CONFLICT", "WON"]
    with ledger(lp, readonly=True) as repo:
        assert repo.read().head.revision == 1
        assert len(repo.read().events) == 1


def test_two_keeper_prepares_one_durable_barrier(tmp_path):
    lp, hp = stores(tmp_path)

    def prepare(number):
        with keeper(lp, hp) as h:
            h.prepare(candidate(number=number), expected=Head())
        return "WON"

    assert sorted(concurrent([lambda: prepare(100), lambda: prepare(101)])) == ["CONFLICT", "WON"]
    with keeper(lp, hp) as h:
        assert h.read().state == "COMMISSIONING_PENDING"
        assert h.read().head.revision == 1


def test_prepare_vs_confirm_and_restart_reconcile_vs_new_operation(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    wire = candidate(Head(1, first.digest), number=101)
    candidate_event = parse_event(wire, BINDING)
    with keeper(lp, hp) as h:
        h.prepare(wire, expected=h.read().head)
        pending_head = h.read().head
    with ledger(lp) as repo:
        repo.append(wire, expected=Head(1, first.digest))
    after = candidate(Head(2, candidate_event.digest), number=102)
    ready, confirmed = Event(), Event()

    def reconcile():
        ready.wait(timeout=10)
        with keeper(lp, hp) as h:
            h.confirm(candidate_event.operation_id, candidate_event.fingerprint)
        confirmed.set()

    def stale_new_operation():
        ready.set()
        assert confirmed.wait(timeout=10)
        with keeper(lp, hp) as h, pytest.raises(IblaDenied):
            h.prepare(after, expected=pending_head)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(reconcile), pool.submit(stale_new_operation)
        a.result(timeout=15)
        b.result(timeout=15)
    with keeper(lp, hp) as h:
        assert h.read_correlated().confirmed.revision == 2
        assert h.read().head.revision == 4


def test_replay_vs_concurrent_ledger_writer(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    next_wire = candidate(Head(1, first.digest), number=101)
    committed = Event()

    def writer():
        with ledger(lp) as repo:
            repo.append(next_wire, expected=Head(1, first.digest))
        committed.set()

    def replay():
        assert committed.wait(timeout=10)
        with ledger(lp) as repo:
            return repo.append(first.envelope, expected=Head())

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(writer), pool.submit(replay)
        a.result(timeout=15)
        assert b.result(timeout=15) == first
    with ledger(lp, readonly=True) as repo:
        assert len(repo.read().events) == 2


@pytest.mark.parametrize("phase", ["prepared", "appended", "confirmed"])
def test_commit_response_loss_is_not_failed_write_or_blind_retry(tmp_path, phase):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    wire = candidate(Head(1, first.digest), number=101)
    event = parse_event(wire, BINDING)
    with keeper(lp, hp) as h:
        h.prepare(wire, expected=h.read().head)
    if phase != "prepared":
        with ledger(lp) as repo:
            repo.append(wire, expected=Head(1, first.digest))
    if phase == "confirmed":
        with keeper(lp, hp) as h:
            h.confirm(event.operation_id, event.fingerprint)
    # Simulate a caller losing the already-committed response, without undo/retry.
    with pytest.raises(OSError):
        raise OSError("lost response")
    with keeper(lp, hp) as h:
        if phase == "prepared":
            with pytest.raises(IblaDenied):
                h.confirm(event.operation_id, event.fingerprint)
        else:
            assert h.confirm(event.operation_id, event.fingerprint).state == "CONFIRMED"
    with ledger(lp, readonly=True) as repo:
        assert repo.read().head.revision == (1 if phase == "prepared" else 2)


def test_uncertain_exact_existing_event_only_can_confirm(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    wire = candidate(Head(1, first.digest), number=101)
    event = parse_event(wire, BINDING)
    with keeper(lp, hp) as h:
        h.prepare(wire, expected=h.read().head)
    # Existing durable fact, then ambiguous observation/control-state recovery.
    with ledger(lp) as repo:
        repo.append(wire, expected=Head(1, first.digest))
    with keeper(lp, hp) as h:
        h.mark_uncertain(event.operation_id, event.fingerprint)
    with keeper(lp, hp) as h:
        assert h.confirm(event.operation_id, event.fingerprint).state == "CONFIRMED"
    with ledger(lp, readonly=True) as repo:
        assert repo.read().head.revision == 2


def test_cleanup_failure_not_silent_success_or_reusable_repository(tmp_path):
    lp, _ = stores(tmp_path)
    with pytest.raises(OSError, match="close failure"), ledger(lp) as repo:
        repo.read()
        original_close = repo.session.close

        def fail_close():
            original_close()
            raise OSError("close failure")

        repo.session.close = fail_close
    with pytest.raises(IblaDenied):
        repo.read()


def test_attached_and_shadow_temp_databases_deny(tmp_path):
    lp, _ = stores(tmp_path)
    with ledger(lp) as repo:
        repo.session.execute(text("CREATE TEMP TABLE ibla_head (revision INTEGER,digest TEXT)"))
        with pytest.raises(IblaDenied):
            repo.read()
    with ledger(lp) as repo:
        repo.session.execute(text("ATTACH DATABASE ':memory:' AS surprise"))
        with pytest.raises(IblaDenied):
            repo.read()


def test_simultaneous_prepare_vs_confirm_does_not_skip_barrier(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    wire = candidate(Head(1, first.digest), number=101)
    event = parse_event(wire, BINDING)
    with keeper(lp, hp) as h:
        h.prepare(wire, expected=h.read().head)
        pending_head = h.read().head
    with ledger(lp) as repo:
        repo.append(wire, expected=Head(1, first.digest))

    def confirm():
        with keeper(lp, hp) as h:
            h.confirm(event.operation_id, event.fingerprint)
        return "CONFIRMED"

    def prepare():
        with keeper(lp, hp) as h:
            h.prepare(candidate(Head(2, event.digest), number=102), expected=pending_head)
        return "UNEXPECTED"

    results = concurrent([confirm, prepare])
    assert results[1] == "CONFLICT"
    assert results[0] in {"CONFIRMED", "CONFLICT"}
    # A busy confirmation is safely reconciled by exact existing L, never reappend.
    with keeper(lp, hp) as h:
        assert h.confirm(event.operation_id, event.fingerprint).state == "CONFIRMED"
        assert h.read().head.revision == 4


def test_reconciliation_io_failure_retains_pending_and_committed_fact(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    wire = candidate(Head(1, first.digest), number=101)
    event = parse_event(wire, BINDING)
    with keeper(lp, hp) as h:
        h.prepare(wire, expected=h.read().head)
    with ledger(lp) as repo:
        repo.append(wire, expected=Head(1, first.digest))
    with (
        keeper(lp, hp) as h,
        patch.object(h._ledger_reader, "read", side_effect=OSError("private")),
        pytest.raises(IblaDenied, match="^IBLA_UNAVAILABLE$"),
    ):
        h.confirm(event.operation_id, event.fingerprint)
    with keeper(lp, hp) as h:
        assert h.read().state == "PREPARED"
        assert h.confirm(event.operation_id, event.fingerprint).state == "CONFIRMED"
