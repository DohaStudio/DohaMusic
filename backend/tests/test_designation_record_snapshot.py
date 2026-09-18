"""Disposable raw records and witness mechanics; NEVER actual designation proof."""

import copy
import os
import pickle
from dataclasses import replace
from unittest.mock import Mock

import pytest

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.designation_snapshot import (
    DESIGNATION_RECORD_FILE,
    _DesignationRecordSnapshots,
)
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.witness_lifetime import WitnessLifetimeDenied
from backend.tests.test_bootstrap_private_pin_reader import fixture, native, witness_check


def setup(fx, tmp_path):
    pin, args, *_ = fx
    path = tmp_path / DESIGNATION_RECORD_FILE
    path.write_bytes(b"record")
    reader = _DesignationRecordSnapshots(trusted_root=str(tmp_path), pin_reader=pin)
    return reader, path, args


def require(reader, handle, fx, **changes):
    _, args, _, _, attempt, witness, _ = fx
    values = dict(
        attempt=attempt,
        witness=witness,
        freshly_verified_binding=args["expected"],
        exact_scope=args["expected"].affected_scopes[0],
    )
    values.update(changes)
    reader._require_current_snapshot(handle, **values)


def test_native_live_record_is_not_authority_and_exit_invalidates(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, args = setup(fx, tmp_path)
        with fx[0]._open_facts(**args) as facts:
            with reader._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as handle:
                require(reader, handle, fx)
                assert repr(handle) == "<opaque deployment handle>"
                for serialize in (copy.copy, copy.deepcopy, pickle.dumps):
                    with pytest.raises(TypeError):
                        serialize(handle)
                with pytest.raises(OSError):
                    path.write_bytes(b"replacement")
                with pytest.raises(OSError):
                    path.rename(tmp_path / "renamed.txt")
                with pytest.raises(CurrentnessUnavailable):
                    UnavailableCurrentnessPorts().revalidate_private_currentness_witness(handle)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)
        path.write_bytes(b"closed")
        assert not reader._snapshots


@pytest.mark.parametrize("invalid", [None, True, {}, object(), "copied"])
def test_original_live_pin_context_required_and_denial_abandons(tmp_path, invalid):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, args = setup(fx, tmp_path)
        with fx[0]._open_facts(**args) as facts:
            supplied = copy.deepcopy(facts) if invalid == "copied" else invalid
            with (
                pytest.raises(PrivateFactsDenied),
                reader._open_record(
                    lease=args["lease"], session=args["session"], pin_facts=supplied
                ),
            ):
                pytest.fail("public/malformed/copied pin facts became live source identity")
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


@pytest.mark.parametrize(
    "raw",
    [b"wrong", b"", b" ", b"\xff", b"\x00", b"\xef\xbb\xbfrecord", b"x" * 1_048_577],
    ids=lambda raw: f"size-{len(raw)}",
)
def test_missing_wrong_digest_or_malformed_record_never_allows(tmp_path, raw):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, args = setup(fx, tmp_path)
        path.write_bytes(raw)
        with fx[0]._open_facts(**args) as facts:
            with (
                pytest.raises(PrivateFactsDenied),
                reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
            ):
                pytest.fail("unverified raw record became valid snapshot")
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        True,
        {},
        object(),
        "designation",
        "fingerprint",
        "scope",
        "revision",
        "witness",
        "attempt",
    ],
)
def test_currentness_mismatch_permanently_invalidates(tmp_path, invalid):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, args = setup(fx, tmp_path)
        with (
            fx[0]._open_facts(**args) as facts,
            reader._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as handle,
        ):
            changes = {"freshly_verified_binding": invalid}
            if invalid == "designation":
                changes = {
                    "freshly_verified_binding": replace(
                        args["expected"], deployment_owner_ref="different/owner"
                    )
                }
            elif invalid == "fingerprint":
                changes = {
                    "freshly_verified_binding": replace(
                        args["expected"], designation_record_digest="sha256:" + "0" * 64
                    )
                }
            elif invalid == "scope":
                changes = {"exact_scope": ("not-a-uuid",) * 3}
            elif invalid == "revision":
                head = replace(args["expected"].journal, revision=2, trust_revision=2)
                changes = {
                    "freshly_verified_binding": replace(
                        args["expected"], journal=head, installed_pin=head
                    )
                }
            elif invalid in ("attempt", "witness"):
                changes = {invalid: object()}
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx, **changes)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


@pytest.mark.parametrize("attack", ["missing", "hardlink", "replacement", "directory"])
def test_fixed_source_substitution_denied(tmp_path, attack):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, args = setup(fx, tmp_path)
        if attack == "hardlink":
            os.link(path, tmp_path / "duplicate.txt")
        else:
            path.unlink()
            if attack == "replacement":
                path.write_bytes(b"replacement")
            elif attack == "directory":
                path.mkdir()
        with (
            fx[0]._open_facts(**args) as facts,
            pytest.raises(PrivateFactsDenied),
            reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
        ):
            pytest.fail("substituted source accepted")


@pytest.mark.parametrize("first_denied", [False, True])
def test_ended_or_rejected_record_context_cannot_reuse_lease(tmp_path, first_denied):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, args = setup(fx, tmp_path)
        with fx[0]._open_facts(**args) as facts:
            kwargs = dict(lease=args["lease"], session=args["session"], pin_facts=facts)
            if first_denied:
                path.write_bytes(b"wrong")
                with pytest.raises(PrivateFactsDenied), reader._open_record(**kwargs):
                    pytest.fail("wrong source accepted")
                path.write_bytes(b"record")
            else:
                with reader._open_record(**kwargs) as handle:
                    require(reader, handle, fx)
            with pytest.raises(PrivateFactsDenied), reader._open_record(**kwargs):
                pytest.fail("ended/rejected record lease was reused")


def test_caller_transaction_change_and_foreign_snapshot_denied(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, args = setup(fx, tmp_path)
        other = _DesignationRecordSnapshots(trusted_root=str(tmp_path), pin_reader=fx[0])
        with (
            fx[0]._open_facts(**args) as facts,
            reader._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as handle,
        ):
            with pytest.raises(PrivateFactsDenied):
                require(other, handle, fx)
            require(reader, handle, fx)
            args["session"].rollback()
            args["session"].begin()
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)


@pytest.mark.parametrize("read_result", [False, True])
def test_record_native_read_error_or_partial_read_denies(tmp_path, monkeypatch, read_result):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, args = setup(fx, tmp_path)
        monkeypatch.setattr(reader._files._api, "ReadFile", Mock(return_value=read_result))
        with fx[0]._open_facts(**args) as facts:
            with (
                pytest.raises(PrivateFactsDenied),
                reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
            ):
                pytest.fail("failed or short source read accepted")
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


def test_record_failed_cleanup_retains_handles_and_invalidates(tmp_path, monkeypatch):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, args = setup(fx, tmp_path)
        close = reader._files._api.CloseHandle
        try:
            with fx[0]._open_facts(**args) as facts:
                with (
                    pytest.raises(PrivateFactsDenied),
                    reader._open_record(
                        lease=args["lease"], session=args["session"], pin_facts=facts
                    ) as handle,
                ):
                    require(reader, handle, fx)
                    monkeypatch.setattr(reader._files._api, "CloseHandle", lambda h: False)
                assert reader._files._quarantine
                assert not reader._snapshots
                with pytest.raises(PrivateFactsDenied):
                    require(reader, handle, fx)
        finally:
            monkeypatch.setattr(reader._files._api, "CloseHandle", close)
            reader._files._cleanup_failed_snapshots()
        path.write_bytes(b"cleanup complete")


def test_closed_original_pin_facts_are_not_live_source(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, args = setup(fx, tmp_path)
        with fx[0]._open_facts(**args) as facts:
            pass
        with (
            pytest.raises(PrivateFactsDenied),
            reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
        ):
            pytest.fail("original but closed pin snapshot accepted")


def test_consumer_exception_invalidates_snapshot_and_witness(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, args = setup(fx, tmp_path)
        with fx[0]._open_facts(**args) as facts:
            with (
                pytest.raises(ValueError, match="consumer"),
                reader._open_record(
                    lease=args["lease"], session=args["session"], pin_facts=facts
                ) as handle,
            ):
                raise ValueError("consumer")
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
