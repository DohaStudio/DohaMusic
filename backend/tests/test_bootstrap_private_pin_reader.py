"""Native isolated file/lease fixtures; no actual trust store/keys/ceremony."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
import rfc8785
from sqlalchemy.orm import Session

from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.private_pin_reader import _PrivatePinFactsReader
from backend.bootstrap_authority.windows_fact_files import (
    PIN_FACTS_FILE,
    _root_components,
    _WindowsFactFiles,
)
from backend.bootstrap_authority.windows_serialization import _WindowsCeremonySerialization
from backend.bootstrap_authority.witness_lifetime import (
    WitnessLifetimeDenied,
    _ProviderWitnessLifetime,
)
from backend.tests.test_bootstrap_pin_facts import INSTALLATION_FP, value
from backend.tests.test_bootstrap_witness_lifetime import binding


def native():
    if sys.platform == "win32":
        return True
    with pytest.raises(PrivateFactsDenied):
        _WindowsFactFiles("Z:\\isolated-test")
    return False


@contextmanager
def fixture(tmp_path):
    current = replace(binding(), affected_scopes=(tuple(str(uuid4()) for _ in range(3)),))
    data = value(current)
    data["installation_id"] = current.affected_scopes[0][0]
    path = tmp_path / PIN_FACTS_FILE
    path.write_bytes(rfc8785.dumps(data))
    lifetime = _ProviderWitnessLifetime()
    provider = _WindowsCeremonySerialization(lifetime)
    reader = _PrivatePinFactsReader(trusted_root=str(tmp_path), serialization=provider)
    with Session() as session:
        session.begin()
        lease = provider._acquire(scopes=current.affected_scopes, session=session)
        attempt = lifetime._begin_after_verified_lease(
            lease=lease, session=session, binding=current
        )
        witness = lifetime._register_after_independent_currentness(attempt)
        args = dict(
            lease=lease,
            session=session,
            expected=current,
            installation_id=current.affected_scopes[0][0],
            installation_proof_key_fingerprint=INSTALLATION_FP,
        )
        try:
            yield reader, args, path, lifetime, attempt, witness, provider
        finally:
            session.rollback()
            provider._release(lease)
            reader._files._cleanup_failed_snapshots()


def witness_check(fx):
    _, args, _, lifetime, attempt, witness, _ = fx
    lifetime._require_live_binding(
        attempt=attempt,
        witness=witness,
        lease=args["lease"],
        session=args["session"],
        freshly_verified_binding=args["expected"],
        exact_scope=args["expected"].affected_scopes[0],
    )


@pytest.mark.parametrize(
    "root",
    [
        None,
        True,
        "",
        "relative",
        "Z:relative",
        "Z:\\",
        "\\\\server\\share",
        "\\\\?\\Z:\\root",
        "Z:/root",
        "Z:\\root\\..\\other",
        "Z:\\root\\.",
        "Z:\\root.",
        "Z:\\root ",
        "Z:\\CON",
        "Z:\\AUX.txt",
        "Z:\\COM1",
        "Z:\\LPT9",
        "Z:\\root:stream",
        "Z:\\PROGRA~1",
        "Z:\\한글",
        "Z:\\" + "x" * 260,
    ],
)
def test_no_untrusted_or_ambiguous_root(root):
    with pytest.raises(PrivateFactsDenied):
        _root_components(root)


def test_unsupported_and_no_request_provider_fallback():
    native()
    with pytest.raises(PrivateFactsDenied):
        _PrivatePinFactsReader(trusted_root="Z:\\isolated-test", serialization=object())


def test_native_stable_snapshot_blocks_write_and_replacement(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, args, path, *_ = fx
        witness_check(fx)
        with reader._open_facts(**args) as facts:
            assert facts.binding == args["expected"]
            with pytest.raises(OSError):
                path.write_bytes(b"malformed")
            with pytest.raises(OSError):
                path.rename(tmp_path / "replacement.json")
            with pytest.raises(OSError):
                tmp_path.rename(tmp_path.with_name(tmp_path.name + "-moved"))
            witness_check(fx)
        with pytest.raises(WitnessLifetimeDenied):
            witness_check(fx)
        # File locks are released at context exit, DTO is not a surviving witness.
        path.write_bytes(b"malformed")


@pytest.mark.parametrize(
    "invalid", ["missing", "malformed", "stale", "oversize", "empty", "directory"]
)
def test_no_private_evidence_fallback_and_witness_abandon(tmp_path, invalid):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, args, path, *_ = fx
        if invalid in ("missing", "directory"):
            path.unlink()
            if invalid == "directory":
                path.mkdir()
        elif invalid == "oversize":
            path.write_bytes(b" " * 1_048_577)
        elif invalid == "empty":
            path.write_bytes(b"")
        elif invalid == "stale":
            data = value(args["expected"])
            data["installation_id"] = args["installation_id"]
            data["pin"]["head_digest"] = "sha256:" + "0" * 64
            path.write_bytes(rfc8785.dumps(data))
        else:
            path.write_bytes(b"malformed")
        with (
            pytest.raises(PrivateFactsDenied, match="^DEPLOYMENT_PRIVATE_FACTS_DENIED$"),
            reader._open_facts(**args),
        ):
            pytest.fail("unavailable/malformed private data returned facts")
        with pytest.raises(WitnessLifetimeDenied):
            witness_check(fx)


@pytest.mark.parametrize("invalid", [None, True, {}, object()])
def test_malformed_expectation_cannot_reactivate_witness(tmp_path, invalid):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, args, *_ = fx
        with pytest.raises(PrivateFactsDenied), reader._open_facts(**{**args, "expected": invalid}):
            pytest.fail("malformed expected authority accepted")
        with pytest.raises(WitnessLifetimeDenied):
            witness_check(fx)


def test_hardlink_substitution_denied(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, args, path, *_ = fx
        os.link(path, tmp_path / "hardlink.json")
        with pytest.raises(PrivateFactsDenied), reader._open_facts(**args):
            pytest.fail("multiple-link private file accepted")


def test_junction_ancestor_denied(tmp_path):
    if not native():
        return
    target, alias = tmp_path / "target", tmp_path / "alias"
    target.mkdir()
    (target / PIN_FACTS_FILE).write_bytes(rfc8785.dumps(value()))
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(alias), str(target)], capture_output=True, check=False
    )
    assert result.returncode == 0, "isolated junction creation failed"
    with pytest.raises(PrivateFactsDenied), _WindowsFactFiles(str(alias))._snapshot():
        pytest.fail("junction trusted-root component accepted")


def test_replaced_file_before_open_is_checked_again(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, args, path, *_ = fx
        old = path.with_name("old.json")
        path.rename(old)
        path.write_bytes(b"malformed replacement")
        with pytest.raises(PrivateFactsDenied), reader._open_facts(**args):
            pytest.fail("old cached file data used")


def test_transaction_change_during_read_denied(tmp_path, monkeypatch):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, args, *_ = fx
        snapshot = reader._files._snapshot

        @contextmanager
        def change_transaction():
            with snapshot() as raw:
                args["session"].rollback()
                args["session"].begin()
                yield raw

        monkeypatch.setattr(reader._files, "_snapshot", change_transaction)
        with pytest.raises(PrivateFactsDenied), reader._open_facts(**args):
            pytest.fail("replaced caller transaction accepted after I/O")


def test_native_concurrent_reads_block_mutation(tmp_path):
    if not native():
        return
    path = tmp_path / PIN_FACTS_FILE
    raw = rfc8785.dumps(value())
    path.write_bytes(raw)
    with (
        _WindowsFactFiles(str(tmp_path))._snapshot() as first,
        ThreadPoolExecutor(max_workers=2) as executor,
    ):

        def read():
            with _WindowsFactFiles(str(tmp_path))._snapshot() as second:
                return second

        assert executor.submit(read).result() == first == raw
        with pytest.raises(OSError):
            executor.submit(path.write_bytes, b"changed").result()


def test_snapshot_close_failure_retains_handle_for_explicit_cleanup(tmp_path, monkeypatch):
    if not native():
        return
    path = tmp_path / PIN_FACTS_FILE
    path.write_bytes(rfc8785.dumps(value()))
    files = _WindowsFactFiles(str(tmp_path))
    close = files._api.CloseHandle
    with pytest.raises(PrivateFactsDenied), files._snapshot():
        monkeypatch.setattr(files._api, "CloseHandle", lambda handle: False)
    assert files._quarantine
    monkeypatch.setattr(files._api, "CloseHandle", close)
    files._cleanup_failed_snapshots()
    assert not files._quarantine
    path.write_bytes(b"cleanup completed")


@pytest.mark.parametrize("native_result", [False, True])
def test_partial_read_or_native_read_error_never_allow(tmp_path, monkeypatch, native_result):
    if not native():
        return
    (tmp_path / PIN_FACTS_FILE).write_bytes(rfc8785.dumps(value()))
    files = _WindowsFactFiles(str(tmp_path))
    monkeypatch.setattr(files._api, "ReadFile", Mock(return_value=native_result))
    with pytest.raises(PrivateFactsDenied), files._snapshot():
        pytest.fail("native read error or short read became allow")
