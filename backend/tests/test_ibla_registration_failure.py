"""Deterministic failure boundaries and actual spawned-process restart facts."""

import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event

import pytest

from backend.bootstrap_authority.ibla.contracts import IblaConflict, IblaDenied
from backend.bootstrap_authority.ibla.registration_owners import _Owners
from backend.bootstrap_authority.ibla.registration_reconciliation import (
    _OriginalReconciliationReader,
)
from backend.bootstrap_authority.ibla.registration_source import _RegistrationOriginals
from backend.bootstrap_authority.ibla.registration_writer import _RegistrationCommitWriter
from backend.bootstrap_authority.ibla.source_verifier import _IblaSourceVerifier
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.tests.ibla_registration_support import registration_fixture
from backend.tests.ibla_source_support import verified
from backend.tests.ibla_support import keeper, ledger


def _child(setup, originals, proof_bytes, stage):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    proof = Ed25519PrivateKey.from_private_bytes(proof_bytes)
    writer = _RegistrationCommitWriter(originals)
    v = _IblaSourceVerifier(setup, consumer=writer)
    original = _Owners.checkpoint

    def checkpoint(self, action, *args, **kwargs):
        if action == "prepare" and stage == "before-prepare":
            os._exit(0)
        if action == "confirm" and stage == "appended":
            os._exit(0)
        result = original(self, action, *args, **kwargs)
        if (action == "prepare" and stage == "prepared") or (
            action == "confirm" and stage == "confirmed"
        ):
            os._exit(0)
        return result

    _Owners.checkpoint = checkpoint
    original_call = _RegistrationCommitWriter.__call__

    def final_handoff(self, capability):
        if stage == "delivered-before-prepare":
            record = self._provider._lookup(capability, "capability")
            assert record.delivered and record.delivering
            # Same original failpoint: immediately after final delivery, before L append.
            assert record.writer_prepared is not None
            os._exit(0)
        return original_call(self, capability)

    _RegistrationCommitWriter.__call__ = final_handoff
    with v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    os._exit(2)


def test_unknown_restart_before_prepare_cannot_retry_original_operation(tmp_path):
    """Original failed final-handoff crash: ADR-112 makes H durable BEFORE it."""
    _, proof, paths, _, setup, originals, _, r, _, binding = registration_fixture(tmp_path)
    before = tuple(p.read_bytes() for p in paths)
    process = multiprocessing.get_context("spawn").Process(
        target=_child,
        args=(setup, originals, proof.private_bytes_raw(), "delivered-before-prepare"),
    )
    process.start()
    process.join(30)
    if process.is_alive():
        process.terminate()
        process.join(10)
        pytest.fail("fixture process failed to finish")
    assert process.exitcode == 0
    assert before[:-1] == tuple(p.read_bytes() for p in paths[:-1])
    assert before[-1] != paths[-1].read_bytes()
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        hv, lv = repo.read(), repo._ledger()
    from backend.bootstrap_authority.ibla.registration_codec import parse_event

    assert hv.state == "PREPARED" and lv.head.revision == 1
    e = parse_event(hv.pending, binding)
    assert e.operation_id == r["operation_id"]
    reader = _OriginalReconciliationReader(setup)
    assert not reader.read(e.operation_id, e.fingerprint).post
    with pytest.raises(IblaDenied):
        reader.confirm_existing(e.operation_id, e.fingerprint)
    fresh = _IblaSourceVerifier(setup, consumer=_RegistrationCommitWriter(originals))
    with pytest.raises(IblaDenied), fresh.observe() as context:
        fresh.handoff(fresh.mint(verified(fresh, proof, context)))


def test_pre_boundary_restart_allows_only_fresh_complete_attempt(tmp_path):
    _, proof, paths, _, setup, originals, _, _, _, binding = registration_fixture(tmp_path)
    before = tuple(p.read_bytes() for p in paths)
    process = multiprocessing.get_context("spawn").Process(
        target=_child,
        args=(setup, originals, proof.private_bytes_raw(), "before-prepare"),
    )
    process.start()
    process.join(30)
    if process.is_alive():
        process.terminate()
        process.join(10)
        pytest.fail("fixture process failed to finish")
    assert process.exitcode == 0
    assert before == tuple(p.read_bytes() for p in paths)
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        assert repo.read().state == "CONFIRMED"
        assert repo.read().pending is None and repo._ledger().head.revision == 1
    fresh = _IblaSourceVerifier(setup, consumer=_RegistrationCommitWriter(originals))
    with fresh.observe() as context:
        # A new challenge/proof/observation/lease/object, never the exited handle.
        result = fresh.handoff(fresh.mint(verified(fresh, proof, context)))
        assert result.post and result.current_h_state == "CONFIRMED"
    with ledger(paths[-2], readonly=True, binding=binding, version=2) as repo:
        assert len(repo.read().events) == 2


@pytest.mark.parametrize("stage", ["prepared", "appended", "confirmed"])
def test_process_exit_restart_never_resurrects_cap(tmp_path, stage):
    _, proof, paths, _, setup, originals, _, r, _, binding = registration_fixture(tmp_path)
    process = multiprocessing.get_context("spawn").Process(
        target=_child, args=(setup, originals, proof.private_bytes_raw(), stage)
    )
    process.start()
    process.join(30)
    if process.is_alive():
        process.terminate()
        process.join(10)
        pytest.fail("fixture process failed to finish")
    assert process.exitcode == 0
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        hv = repo.read()
        lv = repo._ledger()
    from backend.bootstrap_authority.ibla.registration_codec import parse_event

    wire = hv.pending if hv.pending is not None else lv.events[-1].envelope
    event = parse_event(wire, binding)
    before = paths[-2].read_bytes()
    reader = _OriginalReconciliationReader(setup)
    result = reader.read(r["operation_id"], event.fingerprint)
    assert result.post == (stage != "prepared")
    if stage == "prepared":
        with pytest.raises(IblaDenied):
            reader.confirm_existing(r["operation_id"], event.fingerprint)
        assert result.current_h_state == "PREPARED"
    else:
        assert (
            reader.confirm_existing(r["operation_id"], event.fingerprint).current_h_state
            == "CONFIRMED"
        )
    assert before == paths[-2].read_bytes()
    with pytest.raises(IblaConflict):
        reader.read(r["operation_id"], digest(b"different fingerprint"))
    fresh = _IblaSourceVerifier(setup, consumer=_RegistrationCommitWriter(originals))
    with pytest.raises(IblaDenied), fresh.observe():
        pytest.fail("pending or POST minted fresh source")


@pytest.mark.parametrize("index", [0, 1])
def test_committed_response_loss_has_read_only_resolution(tmp_path, monkeypatch, index):
    v, proof, paths, _, setup, _, _, r, _, binding = registration_fixture(tmp_path)
    original = _Owners._write

    @contextmanager
    def response_loss(self, selected):
        with original(self, selected) as session:
            yield session
        if selected == index:
            raise OSError("private fixture response lost")

    monkeypatch.setattr(_Owners, "_write", response_loss)
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        v.handoff(cap)
    monkeypatch.setattr(_Owners, "_write", original)
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        hv = repo.read()
    from backend.bootstrap_authority.ibla.registration_codec import parse_event

    e = parse_event(hv.pending, binding)
    before = paths[-2].read_bytes()
    reader = _OriginalReconciliationReader(setup)
    result = reader.read(r["operation_id"], e.fingerprint)
    assert result.post == (index == 0)
    assert paths[-2].read_bytes() == before
    with pytest.raises(IblaDenied):
        v.handoff(cap)


def test_cross_thread_invocation_cannot_consume_owner_winner(tmp_path, monkeypatch):
    v, proof, _, _, _, _, writer, *_ = registration_fixture(tmp_path)
    barrier = Barrier(2)
    original = _Owners.checkpoint

    def stage(self, action, *args, **kwargs):
        if action == "prepare":
            barrier.wait(timeout=10)
            barrier.wait(timeout=10)
        return original(self, action, *args, **kwargs)

    monkeypatch.setattr(_Owners, "checkpoint", stage)
    with v.observe() as context:
        cap = v.mint(verified(v, proof, context))

        def foreign():
            barrier.wait(timeout=10)
            with pytest.raises(IblaDenied):
                writer(cap)
            barrier.wait(timeout=10)

        with ThreadPoolExecutor(max_workers=1) as pool:
            attempted = pool.submit(foreign)
            result = v.handoff(cap)
            attempted.result(timeout=10)
        assert result.post


@pytest.mark.parametrize("failure", ["deadline", "revocation", "lease", "source", "transaction"])
def test_live_authority_failure_before_l_commit(tmp_path, monkeypatch, failure):
    v, proof, paths, _, _, originals, writer, _, _, binding = registration_fixture(tmp_path)
    original = writer._append

    def revoke(record, session):
        if failure == "deadline":
            record.writer_deadline = 0
        elif failure == "revocation":
            record.authority.setup = replace(
                originals, delegation_end=datetime.now(UTC) - timedelta(seconds=1)
            )
        elif failure == "lease":
            monkeypatch.setattr(
                record.lease, "require_live", lambda: (_ for _ in ()).throw(IblaDenied())
            )
        elif failure == "source":
            record.source.close()
        else:
            record.writer_transaction = object()
        original(record, session)

    monkeypatch.setattr(writer, "_append", revoke)
    before = paths[-2].read_bytes()
    with pytest.raises(IblaDenied), v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        v.handoff(cap)
    assert paths[-2].read_bytes() == before
    with ledger(paths[-2], readonly=True, binding=binding, version=2) as repo:
        assert repo.read().head.revision == 1


@pytest.mark.parametrize(
    "field",
    [
        "original_digest",
        "delegation_digest",
        "writer_ref",
        "root_key_id",
        "initializer_ref",
        "initializer_key_id",
        "delegation_end",
    ],
)
def test_offline_acceptance_mismatch_fails_closed(tmp_path, field):
    _, proof, paths, _, setup, originals, *_ = registration_fixture(tmp_path)
    value = (
        datetime.now(UTC) - timedelta(seconds=1)
        if field == "delegation_end"
        else digest(b"wrong")
        if field.endswith("digest")
        else "other-subject"
    )
    writer = _RegistrationCommitWriter(replace(originals, **{field: value}))
    v = _IblaSourceVerifier(setup, consumer=writer)
    before = tuple(p.read_bytes() for p in paths)
    with pytest.raises(IblaDenied), v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    assert before == tuple(p.read_bytes() for p in paths)
    assert repr(writer) == "<IBLA registration commit writer>"
    assert repr(originals) == "<IBLA registration originals>"
    assert type(originals) is _RegistrationOriginals


@pytest.mark.parametrize("stage", ["prepare", "confirm"])
def test_independent_h_race_has_one_control_winner(tmp_path, monkeypatch, stage):
    v, proof, paths, _, _, _, _, _, _, binding = registration_fixture(tmp_path)
    barrier = Barrier(2)
    original = _Owners.checkpoint

    def pause(self, action, *args, **kwargs):
        if action == stage:
            barrier.wait(timeout=10)
            barrier.wait(timeout=10)
        return original(self, action, *args, **kwargs)

    monkeypatch.setattr(_Owners, "checkpoint", pause)

    def competing_keeper():
        from backend.bootstrap_authority.ibla.codec import parse_event
        from backend.tests.ibla_support import candidate

        barrier.wait(timeout=10)
        with keeper(*paths[-2:], binding=binding, version=2) as repo:
            hv = repo.read()
            if stage == "prepare":
                repo.prepare(candidate(hv.confirmed, binding=binding), expected=hv.head)
            else:
                e = parse_event(hv.pending, binding, version=2)
                repo.confirm(e.operation_id, e.fingerprint)
        barrier.wait(timeout=10)

    with ThreadPoolExecutor(max_workers=1) as pool:
        other = pool.submit(competing_keeper)
        if stage == "prepare":
            with pytest.raises(IblaConflict), v.observe() as context:
                v.handoff(v.mint(verified(v, proof, context)))
        else:
            with v.observe() as context:
                assert v.handoff(v.mint(verified(v, proof, context))).post
        other.result(timeout=10)
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        assert repo.read().head.revision == (3 if stage == "prepare" else 4)


def test_h_confirm_response_loss_preserves_fresh_confirmed_fact(tmp_path, monkeypatch):
    v, proof, paths, _, setup, _, _, r, _, binding = registration_fixture(tmp_path)
    original = _Owners.checkpoint

    def lost(self, action, *args, **kwargs):
        result = original(self, action, *args, **kwargs)
        if action == "confirm":
            raise OSError("private fixture confirm response lost")
        return result

    monkeypatch.setattr(_Owners, "checkpoint", lost)
    with pytest.raises(IblaDenied), v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    with ledger(paths[-2], readonly=True, binding=binding, version=2) as repo:
        e = repo.read().events[-1]
    result = _OriginalReconciliationReader(setup).read(r["operation_id"], e.fingerprint)
    assert result.post and result.current_h_state == "CONFIRMED"


@pytest.mark.parametrize("role", range(4))
def test_each_registration_native_original_requires_independent_pin(tmp_path, role):
    _, proof, paths, _, setup, originals, *_ = registration_fixture(tmp_path)
    roles = list(originals.roles)
    roles[role] = replace(
        roles[role], policy=replace(roles[role].policy, record_identity=(1, b"x" * 16))
    )
    writer = _RegistrationCommitWriter(replace(originals, roles=tuple(roles)))
    v = _IblaSourceVerifier(setup, consumer=writer)
    before = tuple(p.read_bytes() for p in paths)
    with pytest.raises(IblaDenied), v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    assert before == tuple(p.read_bytes() for p in paths)


@pytest.mark.parametrize(
    "failure",
    ["deadline", "revocation", "lease", "source", "proof", "candidate", "writer", "uncertain"],
)
def test_after_prepare_revalidation_denies_stale_frame_before_final_handoff(
    tmp_path, monkeypatch, failure
):
    v, proof, paths, _, setup, originals, writer, _, _, binding = registration_fixture(tmp_path)
    original = writer._prepare
    delivered = []
    original_call = _RegistrationCommitWriter.__call__

    def consumer(self, cap):
        delivered.append(cap)
        return original_call(self, cap)

    def stale(record):
        original(record)
        assert record.writer_prepared is not None and not record.delivered
        if failure == "deadline":
            record.writer_deadline = 0
        elif failure == "revocation":
            record.authority.setup = replace(
                originals, delegation_end=datetime.now(UTC) - timedelta(seconds=1)
            )
        elif failure == "lease":
            monkeypatch.setattr(
                record.lease, "require_live", lambda: (_ for _ in ()).throw(IblaDenied())
            )
        elif failure == "source":
            record.source.close()
        elif failure == "proof":
            record.verified = None
        elif failure == "candidate":
            record.event = replace(record.event, fingerprint=digest(b"wrong candidate"))
        elif failure == "writer":
            record.writer = object()
        else:
            with keeper(*paths[-2:], binding=binding, version=2) as repo:
                repo.mark_uncertain(record.event.operation_id, record.event.fingerprint)

    monkeypatch.setattr(writer, "_prepare", stale)
    monkeypatch.setattr(_RegistrationCommitWriter, "__call__", consumer)
    before = paths[-2].read_bytes()
    with pytest.raises(IblaDenied), v.observe() as context:
        v.handoff(v.mint(verified(v, proof, context)))
    assert delivered == [] and paths[-2].read_bytes() == before
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        hv, lv = repo.read(), repo._ledger()
    assert hv.state == ("UNCERTAIN" if failure == "uncertain" else "PREPARED")
    assert hv.pending is not None and lv.head.revision == 1
    fresh = _IblaSourceVerifier(setup, consumer=_RegistrationCommitWriter(originals))
    with pytest.raises(IblaDenied), fresh.observe():
        pytest.fail("orphan pending allowed new source")


def test_full_prepared_read_precedes_final_delivery_and_generic_h_prepare_denied(
    tmp_path, monkeypatch
):
    v, proof, paths, _, _, _, writer, _, _, binding = registration_fixture(tmp_path)
    original_call = _RegistrationCommitWriter.__call__

    def at_delivery(self, cap):
        record = self._provider._lookup(cap, "capability")
        assert record.delivered and record.delivering and not record.preparing
        assert record.writer_prepared is not None
        with keeper(*paths[-2:], binding=binding, version=2) as repo:
            hv = repo.read()
            assert hv.head == record.writer_prepared
            assert hv.state == "PREPARED" and hv.pending == record.event.envelope
            assert repo._ledger().head.revision == 1
            with pytest.raises(IblaDenied):
                repo.prepare(record.event.envelope, expected=hv.head)
        return original_call(self, cap)

    with v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        with pytest.raises(IblaDenied):
            writer(cap)
        monkeypatch.setattr(_RegistrationCommitWriter, "__call__", at_delivery)
        assert v.handoff(cap).post


def test_concurrent_final_handoff_keeps_single_owner_winner(tmp_path, monkeypatch):
    v, proof, paths, _, _, _, writer, _, _, binding = registration_fixture(tmp_path)
    started = Event()
    original_prepare = writer._prepare
    with ThreadPoolExecutor(max_workers=1) as pool, v.observe() as context:
        cap = v.mint(verified(v, proof, context))
        futures = []

        def competing_handoff():
            started.set()
            with pytest.raises(IblaConflict):
                v.handoff(cap)

        def prepare(record):
            # Original provider lock is held through the actual durable reservation.
            futures.append(pool.submit(competing_handoff))
            assert started.wait(timeout=10)
            original_prepare(record)

        monkeypatch.setattr(writer, "_prepare", prepare)
        assert v.handoff(cap).post
        futures[0].result(timeout=10)
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        assert repo.read().state == "CONFIRMED" and repo.read().head.revision == 4
        assert len(repo._ledger().events) == 2


def test_reentrant_preparation_cannot_deliver_or_reserve_twice(tmp_path, monkeypatch):
    v, proof, paths, _, _, _, writer, _, _, binding = registration_fixture(tmp_path)
    original_prepare = writer._prepare

    def prepare(record):
        with pytest.raises(IblaConflict):
            v.handoff(record.capability)
        original_prepare(record)

    monkeypatch.setattr(writer, "_prepare", prepare)
    with v.observe() as context:
        assert v.handoff(v.mint(verified(v, proof, context))).post
    with keeper(*paths[-2:], binding=binding, version=2) as repo:
        assert repo.read().head.revision == 4
        assert len(repo._ledger().events) == 2
