"""Isolated random namespaces; actual Win32 processes, never deployment ceremony."""

import copy
import ctypes
import multiprocessing
import os
import pickle
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.windows_serialization import (
    _RESERVATIONS,
    CeremonySerializationDenied,
    _KernelMutexes,
    _names,
    _WindowsCeremonySerialization,
)
from backend.bootstrap_authority.witness_lifetime import (
    WitnessLifetimeDenied,
    _ProviderWitnessLifetime,
)
from backend.tests.test_bootstrap_witness_lifetime import binding


def scopes():
    return (tuple(str(uuid4()) for _ in range(3)),)


def platform_available():
    if sys.platform == "win32":
        return True
    # Executable unsupported-platform fail-closed Gate, no skip or Fake fallback.
    with pytest.raises(CeremonySerializationDenied):
        _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    return False


def child(scope_set, connection, start=None, finish=None):
    with Session() as session:
        session.begin()
        provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
        if start is not None:
            connection.send("ready")
            assert start.wait(10)
        try:
            lease = provider._acquire(scopes=scope_set, session=session)
        except CeremonySerializationDenied:
            connection.send("denied")
            return
        connection.send("acquired")
        if finish is not None:
            assert finish.wait(10)
        elif connection.recv() == "crash":
            os._exit(0)  # Isolated test child only: intentionally no release.
        session.rollback()
        provider._release(lease)


def receive(connection):
    assert connection.poll(10), "test child deadline exceeded"
    return connection.recv()


def join(process):
    process.join(10)
    if process.is_alive():
        process.terminate()  # Only the explicitly created isolated test child.
        process.join(10)
        pytest.fail("test child deadline exceeded")
    assert process.exitcode == 0


@pytest.mark.parametrize(
    "invalid",
    [None, True, (), [], (("invalid", "invalid", "invalid"),), ((),), ((True, 1, 1.0),)],
)
def test_strict_manifest(invalid):
    with pytest.raises(CeremonySerializationDenied):
        _names(invalid)


def test_native_manifest_only_no_custom_equality():
    class Spoof(str):
        def __eq__(self, other):
            return True

        __hash__ = str.__hash__

    scope_set = scopes()
    with pytest.raises(CeremonySerializationDenied):
        _names(((Spoof(scope_set[0][0]), *scope_set[0][1:]),))
    with pytest.raises(CeremonySerializationDenied):
        _names(scope_set * 2)
    with pytest.raises(CeremonySerializationDenied):
        _names(scope_set * 4097)
    second = scopes()[0]
    with pytest.raises(CeremonySerializationDenied):
        _names(tuple(sorted((scope_set[0], second), reverse=True)))


def test_names_bind_exact_installation_and_scope_no_paths():
    original = scopes()
    assert _names(original)[0].startswith("Global\\DohaMusicCeremonyV1_")
    for index in range(3):
        changed = list(original[0])
        changed[index] = str(uuid4())
        assert _names((tuple(changed),)) != _names(original)
    assert _names(original) == _names(original)


def test_unsupported_and_invalid_lifetime():
    platform_available()
    for value in (None, True, object(), binding()):
        with pytest.raises(CeremonySerializationDenied):
            _WindowsCeremonySerialization(value)


@pytest.mark.parametrize("end", ["commit", "rollback", "close"])
def test_transaction_lifetime_and_witness_release(end):
    if not platform_available():
        return
    lifetime = _ProviderWitnessLifetime()
    provider = _WindowsCeremonySerialization(lifetime)
    scope_set = scopes()
    with Session() as session:
        session.begin()
        lease = provider._acquire(scopes=scope_set, session=session)
        current = replace(binding(), affected_scopes=scope_set)
        attempt = lifetime._begin_after_verified_lease(
            lease=lease, session=session, binding=current
        )
        witness = lifetime._register_after_independent_currentness(attempt)
        provider._require_live(lease, session=session, scopes=scope_set)
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError):
                operation(lease)
        assert repr(lease) == "<opaque deployment handle>"
        with pytest.raises(CurrentnessUnavailable):
            UnavailableCurrentnessPorts().revalidate_private_currentness_witness(witness)
        getattr(session, end)()
        with pytest.raises(CeremonySerializationDenied):
            provider._require_live(lease, session=session, scopes=scope_set)
        provider._release(lease)
        session.begin()
        with pytest.raises(WitnessLifetimeDenied):
            lifetime._register_after_independent_currentness(attempt)
        with pytest.raises(CeremonySerializationDenied):
            provider._require_live(lease, session=session, scopes=scope_set)
        fresh = provider._acquire(scopes=scope_set, session=session)
        assert fresh is not lease
        session.rollback()
        provider._release(fresh)


@pytest.mark.parametrize("rejection", ["scope", "savepoint", "premature_release"])
def test_observed_rejection_cannot_reactivate_lease(rejection):
    if not platform_available():
        return
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    scope_set = scopes()
    with Session() as session:
        session.begin()
        lease = provider._acquire(scopes=scope_set, session=session)
        if rejection == "scope":
            with pytest.raises(CeremonySerializationDenied):
                provider._require_live(lease, session=session, scopes=scopes())
        elif rejection == "savepoint":
            with session.begin_nested(), pytest.raises(CeremonySerializationDenied):
                provider._require_live(lease, session=session, scopes=scope_set)
        else:
            with pytest.raises(CeremonySerializationDenied):
                provider._release(lease)
        try:
            with pytest.raises(CeremonySerializationDenied):
                provider._require_live(lease, session=session, scopes=scope_set)
        finally:
            session.rollback()
            provider._release(lease)


def test_recursive_acquire_and_wrong_thread_provider_identity():
    if not platform_available():
        return
    scope_set = scopes()
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    other = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    with Session() as session:
        session.begin()
        lease = provider._acquire(scopes=scope_set, session=session)
        try:
            for contender in (provider, other):
                with pytest.raises(CeremonySerializationDenied):
                    contender._acquire(scopes=scope_set, session=session)
            with pytest.raises(CeremonySerializationDenied):
                other._release(lease)
            with (
                ThreadPoolExecutor(max_workers=1) as executor,
                pytest.raises(CeremonySerializationDenied),
            ):
                executor.submit(provider._release, lease).result()
            provider._require_live(lease, session=session, scopes=scope_set)
        finally:
            session.rollback()
            provider._release(lease)


def test_partial_multi_scope_acquire_cleanup():
    if not platform_available():
        return
    scope_set = tuple(sorted((scopes()[0], scopes()[0])))
    ctx = multiprocessing.get_context("spawn")
    parent, remote = ctx.Pipe()
    process = ctx.Process(target=child, args=((scope_set[1],), remote))
    process.start()
    assert receive(parent) == "acquired"
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    try:
        with Session() as session:
            session.begin()
            with pytest.raises(CeremonySerializationDenied):
                provider._acquire(scopes=scope_set, session=session)
            # Earlier mutex must be released after later scope contention.
            lease = provider._acquire(scopes=(scope_set[0],), session=session)
            session.rollback()
            provider._release(lease)
    finally:
        parent.send("release")
        join(process)
        parent.close()
        remote.close()


@pytest.mark.parametrize("round_number", range(3))
def test_process_race_winner_one(round_number):
    if not platform_available():
        return
    ctx = multiprocessing.get_context("spawn")
    start, finish = ctx.Event(), ctx.Event()
    scope_set = scopes()
    connections, processes = [], []
    try:
        for _ in range(2):
            parent, remote = ctx.Pipe()
            process = ctx.Process(target=child, args=(scope_set, remote, start, finish))
            process.start()
            connections.append((parent, remote))
            processes.append(process)
        assert [receive(pair[0]) for pair in connections] == ["ready", "ready"]
        start.set()
        assert sorted(receive(pair[0]) for pair in connections) == ["acquired", "denied"]
    finally:
        finish.set()
        for process in processes:
            join(process)
        for pair in connections:
            for connection in pair:
                connection.close()


def test_crash_abandoned_denied_then_fresh_restart():
    if not platform_available():
        return
    ctx = multiprocessing.get_context("spawn")
    scope_set = scopes()
    parent, remote = ctx.Pipe()
    process = ctx.Process(target=child, args=(scope_set, remote))
    process.start()
    assert receive(parent) == "acquired"
    # Keep a handle open so process exit does not destroy the named object and
    # erase OS abandonment. This observer does NOT acquire ownership.
    kernel = _KernelMutexes()
    observer = kernel.api.CreateMutexW(None, False, _names(scope_set)[0])
    assert observer
    try:
        parent.send("crash")
        join(process)
        provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
        with Session() as session:
            session.begin()
            with pytest.raises(CeremonySerializationDenied):
                provider._acquire(scopes=scope_set, session=session)
            # New mechanical lease only, NOT fresh evidence/admission authority.
            lease = provider._acquire(scopes=scope_set, session=session)
            session.rollback()
            provider._release(lease)
    finally:
        assert kernel.api.CloseHandle(observer)
        parent.close()
        remote.close()


def test_no_hidden_transaction_calls():
    if not platform_available():
        return
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    with Session() as session:
        transaction = session.begin()
        for method in ("commit", "rollback", "flush"):
            setattr(session, method, Mock(side_effect=AssertionError("hidden transaction call")))
        scope_set = scopes()
        lease = provider._acquire(scopes=scope_set, session=session)
        provider._require_live(lease, session=session, scopes=scope_set)
        transaction.rollback()  # Explicit caller-owned transaction end.
        provider._release(lease)
        assert (
            session.commit.call_count
            == session.rollback.call_count
            == session.flush.call_count
            == 0
        )
        for method in ("commit", "rollback", "flush"):
            delattr(session, method)


def test_kernel_namespace_collision_fails_closed_and_cleans_up():
    if not platform_available():
        return
    from ctypes import wintypes

    kernel = _KernelMutexes()
    kernel.api.CreateEventW.argtypes = [
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel.api.CreateEventW.restype = wintypes.HANDLE
    scope_set = scopes()
    event = kernel.api.CreateEventW(None, False, False, _names(scope_set)[0])
    assert event
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    with Session() as session:
        session.begin()
        try:
            with pytest.raises(CeremonySerializationDenied):
                provider._acquire(scopes=scope_set, session=session)
        finally:
            assert kernel.api.CloseHandle(event)
        # Failed CreateMutex must not leave a reservation or take a local fallback.
        lease = provider._acquire(scopes=scope_set, session=session)
        session.rollback()
        provider._release(lease)


@pytest.mark.parametrize("invalid", ["no_transaction", "savepoint", "forged_lease"])
def test_no_transaction_savepoint_or_forged_lease(invalid):
    if not platform_available():
        return
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    with Session() as session:
        if invalid == "savepoint":
            with (
                session.begin(),
                session.begin_nested(),
                pytest.raises(CeremonySerializationDenied),
            ):
                provider._acquire(scopes=scopes(), session=session)
        elif invalid == "no_transaction":
            with pytest.raises(CeremonySerializationDenied):
                provider._acquire(scopes=scopes(), session=session)
        else:
            with pytest.raises(CeremonySerializationDenied):
                provider._release(object())


def test_premature_release_keeps_process_exclusion_and_invalidates_witness():
    if not platform_available():
        return
    lifetime = _ProviderWitnessLifetime()
    provider = _WindowsCeremonySerialization(lifetime)
    scope_set = scopes()
    with Session() as session:
        session.begin()
        lease = provider._acquire(scopes=scope_set, session=session)
        attempt = lifetime._begin_after_verified_lease(
            lease=lease, session=session, binding=replace(binding(), affected_scopes=scope_set)
        )
        lifetime._register_after_independent_currentness(attempt)
        try:
            with pytest.raises(CeremonySerializationDenied):
                provider._release(lease)
            with pytest.raises(WitnessLifetimeDenied):
                lifetime._register_after_independent_currentness(attempt)
            ctx = multiprocessing.get_context("spawn")
            parent, remote = ctx.Pipe()
            process = ctx.Process(target=child, args=(scope_set, remote))
            process.start()
            try:
                assert receive(parent) == "denied"
                join(process)
            finally:
                parent.close()
                remote.close()
        finally:
            session.rollback()
            provider._release(lease)


def test_partial_cleanup_failure_retains_reservation_and_handle(monkeypatch):
    if not platform_available():
        return
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    scope_set = tuple(sorted((scopes()[0], scopes()[0])))
    acquire, release = provider._kernel.acquire, provider._kernel.release
    captured = []

    def fail_second(name):
        if captured:
            raise CeremonySerializationDenied()
        result = acquire(name)
        captured.append(result)
        return result

    monkeypatch.setattr(provider._kernel, "acquire", fail_second)
    monkeypatch.setattr(
        provider._kernel, "release", Mock(side_effect=CeremonySerializationDenied())
    )
    with Session() as session:
        session.begin()
        try:
            with pytest.raises(CeremonySerializationDenied):
                provider._acquire(scopes=scope_set, session=session)
            assert _names((scope_set[0],))[0] in _RESERVATIONS
        finally:
            monkeypatch.setattr(provider._kernel, "release", release)
            if hasattr(provider, "_cleanup_failed_acquisitions"):
                provider._cleanup_failed_acquisitions()
            else:
                release(captured[0])  # Reproduction-only old implementation cleanup.
    assert all(name not in _RESERVATIONS for name in _names(scope_set))


def test_close_failure_retry_does_not_release_mutex_twice(monkeypatch):
    if not platform_available():
        return
    provider = _WindowsCeremonySerialization(_ProviderWitnessLifetime())
    scope_set = scopes()
    with Session() as session:
        session.begin()
        lease = provider._acquire(scopes=scope_set, session=session)
        session.rollback()
        close = provider._kernel.api.CloseHandle
        monkeypatch.setattr(provider._kernel.api, "CloseHandle", lambda handle: False)
        with pytest.raises(CeremonySerializationDenied):
            provider._release(lease)
        monkeypatch.setattr(provider._kernel.api, "CloseHandle", close)
        provider._release(lease)
