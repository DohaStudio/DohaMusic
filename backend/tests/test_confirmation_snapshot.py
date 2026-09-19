"""Disposable unsigned raw records/partial snapshots, NEVER authentication proof."""

import copy
import os
import pickle
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import Mock

import pytest

from backend.bootstrap_authority.confirmation_snapshot import (
    CONFIRMATION_RECORD_FILE,
    _OriginalConfirmationSnapshots,
)
from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.provisioning_binding import (
    InitializerConfirmationFacts,
    PolicyLineageFacts,
    PolicySnapshotFacts,
    ProvisioningActionFacts,
    policy_snapshot_digest,
)
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.bootstrap_authority.witness_lifetime import WitnessLifetimeDenied
from backend.tests.test_bootstrap_private_pin_reader import fixture, native, witness_check
from backend.tests.test_designation_source_custody import (
    native_acl,
    process_account,
    provision_fixture_acl,
)
from backend.tests.test_designation_source_custody import (
    setup as custody_setup,
)
from backend.tests.test_provisioning_binding import uid

RAW = b"disposable original confirmation\n"


def setup(fx, tmp_path):
    designation, _, owner_text, policy = custody_setup(fx, tmp_path)
    path = tmp_path / CONFIRMATION_RECORD_FILE
    path.write_bytes(RAW)
    provision_fixture_acl(path, process_account())
    files = _WindowsFactFiles(str(tmp_path))
    handle = files._open(str(path), directory=False)
    try:
        identity = files._check(handle, str(path), directory=False)[:2]
    finally:
        files._close([handle])
    reader = _OriginalConfirmationSnapshots(
        trusted_root=str(tmp_path),
        pin_reader=fx[0],
        designation_snapshots=designation,
        confirmation_policy=replace(policy, record_identity=identity),
    )
    return reader, designation, path, owner_text, policy


def values(facts, policy):
    snapshot = PolicySnapshotFacts(
        uid(50), 1, facts.installation_id, facts.installation_proof_key_fingerprint, uid(51), policy
    )
    confirmation = InitializerConfirmationFacts(
        uid(100),
        "original/test",
        digest(RAW),
        "initializer/test",
        uid(200),
        policy_snapshot_digest(snapshot),
        facts,
    )
    action = ProvisioningActionFacts(uid(200), snapshot, confirmation, None)
    lineage = PolicyLineageFacts(uid(52), facts.installation_id, uid(51), (action,), ("ACTIVE",))
    return action, lineage


@contextmanager
def live(fx, reader, designation, policy):
    args = fx[1]
    with (
        fx[0]._open_facts(**args) as facts,
        designation._open_record(
            lease=args["lease"], session=args["session"], pin_facts=facts
        ) as held,
    ):
        action, lineage = values(facts, policy)
        inputs = dict(
            lease=args["lease"],
            session=args["session"],
            pin_facts=facts,
            designation=held,
            action=action,
            lineage=lineage,
        )
        yield inputs


def require(reader, handle, inputs, **changes):
    args = dict(fresh_action=inputs["action"], fresh_lineage=inputs["lineage"])
    args.update(changes)
    reader._require_unchanged(handle, **args)


def test_native_live_snapshot_never_authentication_and_exit_abandons(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, path, _, policy = setup(fx, tmp_path)
        with live(fx, reader, designation, policy) as inputs:
            with reader._open_snapshot(**inputs) as handle:
                require(reader, handle, inputs)
                require(reader, handle, inputs, fresh_action=copy.deepcopy(inputs["action"]))
                for serialize in (copy.copy, copy.deepcopy, pickle.dumps):
                    with pytest.raises(TypeError):
                        serialize(handle)
                with pytest.raises(OSError):
                    path.write_bytes(b"replacement")
                with pytest.raises(OSError):
                    path.rename(tmp_path / "renamed.txt")
                for fn in (
                    UnavailableCurrentnessPorts().admit_with_private_ceremony_witness,
                    UnavailableCurrentnessPorts().revalidate_private_currentness_witness,
                ):
                    with pytest.raises(CurrentnessUnavailable):
                        fn(handle)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)
        assert not reader._records and reader._files._live is None


@pytest.mark.parametrize(
    "raw",
    [b"", b" ", b"\xff", b"\x00", b"\xef\xbb\xbfwrong", b"wrong", b"x" * 1_048_577],
    ids=lambda raw: f"size-{len(raw)}",
)
def test_malformed_or_wrong_exact_digest_never_allows(tmp_path, raw):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, path, _, policy = setup(fx, tmp_path)
        path.write_bytes(raw)
        with live(fx, reader, designation, policy) as inputs:
            with pytest.raises(PrivateFactsDenied), reader._open_snapshot(**inputs):
                pytest.fail("invalid raw confirmation became usable")
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


@pytest.mark.parametrize("field", ["action", "lineage", "pin_facts", "designation"])
def test_public_metadata_substitution_denied(tmp_path, field):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        with live(fx, reader, designation, policy) as inputs:
            inputs[field] = {}
            with pytest.raises(PrivateFactsDenied), reader._open_snapshot(**inputs):
                pytest.fail("public metadata became original live snapshot")
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


def test_custom_action_equality_never_called(tmp_path):
    if not native():
        return

    class Hostile:
        calls = 0

        def __eq__(self, other):
            self.calls += 1
            return True

    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        with live(fx, reader, designation, policy) as inputs:
            hostile = Hostile()
            inputs["action"] = hostile
            with pytest.raises(PrivateFactsDenied), reader._open_snapshot(**inputs):
                pytest.fail("hostile action allowed")
            assert hostile.calls == 0


@pytest.mark.parametrize("attack", ["missing", "hardlink", "replacement", "directory"])
def test_native_file_substitution_denied(tmp_path, attack):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, path, text, policy = setup(fx, tmp_path)
        if attack == "hardlink":
            os.link(path, tmp_path / "alias.txt")
        else:
            path.unlink()
            if attack == "replacement":
                path.write_bytes(RAW)
                native_acl(path, text)
            elif attack == "directory":
                path.mkdir()
        with (
            live(fx, reader, designation, policy) as inputs,
            pytest.raises(PrivateFactsDenied),
            reader._open_snapshot(**inputs),
        ):
            pytest.fail("substituted file accepted")


@pytest.mark.parametrize(
    "change", ["initializer", "confirmation", "anchor", "terminal", "transaction", "thread"]
)
def test_fresh_mismatch_abandons_and_restored_values_cannot_revive(tmp_path, change):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        with (
            live(fx, reader, designation, policy) as inputs,
            reader._open_snapshot(**inputs) as handle,
        ):
            changes = {}
            if change in ("initializer", "confirmation"):
                name = (
                    "initializer_ref" if change == "initializer" else "original_confirmation_digest"
                )
                new_value = "different/initializer" if change == "initializer" else digest(b"other")
                action = replace(
                    inputs["action"],
                    confirmation=replace(inputs["action"].confirmation, **{name: new_value}),
                )
                changes = dict(
                    fresh_action=action, fresh_lineage=replace(inputs["lineage"], actions=(action,))
                )
            elif change == "anchor":
                changes = dict(fresh_lineage=replace(inputs["lineage"], anchor_id=uid(999)))
            elif change == "terminal":
                changes = dict(fresh_lineage=replace(inputs["lineage"], statuses=("REVOKED",)))
            elif change == "transaction":
                fx[1]["session"].rollback()
                fx[1]["session"].begin()
            with pytest.raises(PrivateFactsDenied):
                if change == "thread":
                    with ThreadPoolExecutor(1) as pool:
                        pool.submit(require, reader, handle, inputs).result()
                else:
                    require(reader, handle, inputs, **changes)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


@pytest.mark.parametrize("target", ["confirmation", "designation", "root"])
def test_acl_change_then_restore_never_reactivates(tmp_path, target):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, path, text, policy = setup(fx, tmp_path)
        selected = (
            path
            if target == "confirmation"
            else tmp_path
            if target == "root"
            else tmp_path / "designation-record-v1.txt"
        )
        with (
            live(fx, reader, designation, policy) as inputs,
            reader._open_snapshot(**inputs) as handle,
        ):
            native_acl(selected, text, suffix="(A;;FR;;;WD)")
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
            native_acl(selected, text)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)


@pytest.mark.parametrize("raised", [False, True])
def test_close_failure_retains_handles_and_retry_ownership(tmp_path, monkeypatch, raised):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        original = reader._files._api.CloseHandle
        with live(fx, reader, designation, policy) as inputs:
            with pytest.raises(PrivateFactsDenied), reader._open_snapshot(**inputs) as handle:
                require(reader, handle, inputs)
                monkeypatch.setattr(
                    reader._files._api,
                    "CloseHandle",
                    Mock(side_effect=OSError("injected")) if raised else Mock(return_value=0),
                )
            assert reader._files._quarantine
            supplied = False
            try:
                with reader._files._snapshot():
                    supplied = True
            except PrivateFactsDenied:
                pass
            assert not supplied, "quarantined native transport yielded a new snapshot"
            with pytest.raises(PrivateFactsDenied):
                reader._files._cleanup_failed_snapshots()
            assert reader._files._quarantine
            monkeypatch.setattr(reader._files._api, "CloseHandle", original)
            reader._files._cleanup_failed_snapshots()
            assert not reader._files._quarantine and not reader._records


def test_read_uncertainty_permanently_abandons(tmp_path, monkeypatch):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        with (
            live(fx, reader, designation, policy) as inputs,
            reader._open_snapshot(**inputs) as handle,
        ):
            original = reader._files._api.ReadFile
            monkeypatch.setattr(
                reader._files._api, "ReadFile", Mock(side_effect=OSError("injected"))
            )
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
            monkeypatch.setattr(reader._files._api, "ReadFile", original)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)


@pytest.mark.parametrize("target", ["confirmation", "designation"])
def test_existing_writable_mapping_denied_before_handoff_and_old_lease_stays_rejected(
    tmp_path, target
):
    if not native():
        return
    import ctypes
    from ctypes import wintypes as w

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ptr = ctypes.c_void_p
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ptr, w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CreateFileMappingW.argtypes = [w.HANDLE, ptr, w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR]
    kernel.CreateFileMappingW.restype = w.HANDLE
    kernel.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, ctypes.c_size_t]
    kernel.MapViewOfFile.restype = ptr
    kernel.FlushViewOfFile.argtypes, kernel.FlushViewOfFile.restype = [ptr, ctypes.c_size_t], w.BOOL
    kernel.UnmapViewOfFile.argtypes, kernel.UnmapViewOfFile.restype = [ptr], w.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    with fixture(tmp_path) as fx:
        reader, designation, path, _, policy = setup(fx, tmp_path)
        selected = path if target == "confirmation" else tmp_path / "designation-record-v1.txt"
        raw = RAW if target == "confirmation" else b"record"
        file_handle = kernel.CreateFileW(str(selected), 0xC0000000, 7, None, 3, 0, None)
        assert file_handle not in (None, ptr(-1).value)
        try:
            mapping = kernel.CreateFileMappingW(file_handle, None, 4, 0, 0, None)
            assert mapping
        finally:
            assert kernel.CloseHandle(file_handle)
        view = kernel.MapViewOfFile(mapping, 6, 0, 0, 0)
        try:
            assert view
            ctypes.memmove(view, b"x" * len(raw), len(raw))
            assert kernel.FlushViewOfFile(view, len(raw))
            with (
                pytest.raises(PrivateFactsDenied),
                live(fx, reader, designation, policy) as inputs,
                reader._open_snapshot(**inputs),
            ):
                pytest.fail("existing writable mapping became usable snapshot")
            ctypes.memmove(view, raw, len(raw))
            assert kernel.FlushViewOfFile(view, len(raw))
        finally:
            if view:
                assert kernel.UnmapViewOfFile(view)
            assert kernel.CloseHandle(mapping)
        with pytest.raises(PrivateFactsDenied), live(fx, reader, designation, policy):
            pytest.fail("mapping removal and restored bytes revived old lease")
        with pytest.raises(WitnessLifetimeDenied):
            witness_check(fx)


def test_seek_uncertainty_permanently_abandons(tmp_path, monkeypatch):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        with (
            live(fx, reader, designation, policy) as inputs,
            reader._open_snapshot(**inputs) as handle,
        ):
            original = reader._files._api.SetFilePointerEx
            monkeypatch.setattr(reader._files._api, "SetFilePointerEx", Mock(return_value=0))
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
            monkeypatch.setattr(reader._files._api, "SetFilePointerEx", original)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)


@pytest.mark.parametrize("target", ["confirmation", "designation"])
def test_observed_same_size_read_byte_change_then_api_restore_never_revives(
    tmp_path, monkeypatch, target
):
    if not native():
        return
    import ctypes

    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        with (
            live(fx, reader, designation, policy) as inputs,
            reader._open_snapshot(**inputs) as handle,
        ):
            files = reader._files if target == "confirmation" else designation._files
            original = files._api.ReadFile

            def replaced_read(native_handle, buffer, length, count, overlapped):
                result = original(native_handle, buffer, length, count, overlapped)
                assert result
                ctypes.memmove(buffer, b"x" * (length - 1), length - 1)
                return result

            monkeypatch.setattr(files._api, "ReadFile", replaced_read)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
            assert files._invalid
            monkeypatch.setattr(files._api, "ReadFile", original)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)


def test_in_place_public_lineage_anchor_change_cannot_rebind_original_handle(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, _, _, policy = setup(fx, tmp_path)
        with (
            live(fx, reader, designation, policy) as inputs,
            reader._open_snapshot(**inputs) as handle,
        ):
            lineage = inputs["lineage"]
            original = lineage.anchor_id
            object.__setattr__(lineage, "anchor_id", uid(999))
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
            object.__setattr__(lineage, "anchor_id", original)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, inputs)
