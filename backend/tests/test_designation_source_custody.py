"""Disposable file ACLs only; OS SID is NOT designated human/ceremony proof."""

import ctypes
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock

import pytest

from backend.bootstrap_authority.designation_snapshot import _DesignationRecordSnapshots
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.source_custody import (
    SourceCustodyPolicy,
    _CustodyDesignationRecordFiles,
)
from backend.bootstrap_authority.witness_lifetime import WitnessLifetimeDenied
from backend.tests.test_bootstrap_private_pin_reader import fixture, native, witness_check
from backend.tests.test_designation_record_snapshot import require

ACCOUNT = b"\x01\x05" + b"\x00" * 5 + b"\x05" + struct.pack("<IIIII", 21, 1, 2, 3, 1001)
SYSTEM = b"\x01\x01" + b"\x00" * 5 + b"\x05" + struct.pack("<I", 18)
ADMINISTRATORS = b"\x01\x02" + b"\x00" * 5 + b"\x05" + struct.pack("<II", 32, 544)
BUILTIN_ACCOUNT = ACCOUNT[:-4] + struct.pack("<I", 500)


def acl(*sids):
    entries = b"".join(struct.pack("<BBHI", 0, 0, 8 + len(sid), 0x1F01FF) + sid for sid in sids)
    return struct.pack("<BBHHH", 2, 0, 8 + len(entries), len(sids), 0) + entries


def policy():
    return SourceCustodyPolicy(
        (1, b"r" * 16),
        (1, b"f" * 16),
        ACCOUNT,
        tuple(sorted((ACCOUNT, SYSTEM))),
        acl(ACCOUNT, SYSTEM),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"root_identity": (True, b"r" * 16)},
        {"record_identity": (1.0, b"f" * 16)},
        {"root_identity": (1, b"\x00" * 16)},
        {"owner_sid": True},
        {"allowed_sids": []},
        {"allowed_sids": (ACCOUNT, ACCOUNT)},
        {"dacl": b""},
        {"dacl": b"\x00" * 8},
        {"dacl": acl(ACCOUNT, SYSTEM) + b"extra"},
        {"dacl": acl(ACCOUNT)},
        {"dacl": acl(ACCOUNT, ACCOUNT)},
        {"dacl": acl(SYSTEM)},
    ],
)
def test_strict_public_policy_not_authority(change):
    with pytest.raises(PrivateFactsDenied):
        replace(policy(), **change)


@pytest.mark.parametrize(
    "offset,value", [(0, 4), (1, 1), (8, 1), (8, 5), (9, 16), (9, 3), (15, 128)]
)
def test_unsupported_acl_revision_flags_ace_mask_deny(offset, value):
    raw = bytearray(policy().dacl)
    raw[offset] = value
    with pytest.raises(PrivateFactsDenied):
        replace(policy(), dacl=bytes(raw))


def test_broad_sid_and_custom_comparison_never_accepted():
    class Hostile(bytes):
        def __hash__(self):
            pytest.fail("custom hash called")

        def __eq__(self, other):
            pytest.fail("custom equality called")

    for sid in (
        Hostile(ACCOUNT),
        BUILTIN_ACCOUNT,
        b"\x01\x01" + b"\x00" * 6 + struct.pack("<I", 0),
        b"\x01\x02" + b"\x00" * 5 + b"\x05" + struct.pack("<II", 32, 544),
    ):
        with pytest.raises(PrivateFactsDenied):
            replace(policy(), owner_sid=sid)
    native()


def native_acl(path, owner_text, *, suffix="", protected=True, set_owner=False):
    """Set ONLY disposable temp owner/DACL, no parent/user/real store ACL."""
    from ctypes import wintypes as w

    api, kernel = (
        ctypes.WinDLL("advapi32", use_last_error=True),
        ctypes.WinDLL("kernel32", use_last_error=True),
    )
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        w.LPCWSTR,
        w.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(w.DWORD),
    ]
    api.SetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.c_void_p]
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [ctypes.c_void_p], ctypes.c_void_p
    descriptor = ctypes.c_void_p()
    text = (f"O:{owner_text}" if set_owner else "") + (
        f"D:{'P' if protected else ''}(A;;FA;;;{owner_text})(A;;FA;;;SY){suffix}"
    )
    assert api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        text, 1, ctypes.byref(descriptor), None
    )
    try:
        assert api.SetFileSecurityW(
            str(path), 4 | int(set_owner) | (0x80000000 if protected else 0x20000000), descriptor
        ), (owner_text, ctypes.get_last_error(), ctypes.FormatError(ctypes.get_last_error()))
    finally:
        assert not kernel.LocalFree(descriptor)


def owner(path):
    from ctypes import wintypes as w

    api, kernel = (
        ctypes.WinDLL("advapi32", use_last_error=True),
        ctypes.WinDLL("kernel32", use_last_error=True),
    )
    ptr = ctypes.c_void_p
    api.GetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, ptr, w.DWORD, ctypes.POINTER(w.DWORD)]
    api.GetSecurityDescriptorOwner.argtypes = [ptr, ctypes.POINTER(ptr), ctypes.POINTER(w.BOOL)]
    api.GetLengthSid.argtypes, api.GetLengthSid.restype = [ptr], w.DWORD
    api.ConvertSidToStringSidW.argtypes = [ptr, ctypes.POINTER(ptr)]
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [ptr], ptr
    needed = w.DWORD()
    api.GetFileSecurityW(str(path), 1, None, 0, ctypes.byref(needed))
    buffer = ctypes.create_string_buffer(needed.value)
    assert api.GetFileSecurityW(str(path), 1, buffer, len(buffer), ctypes.byref(needed))
    sid, defaulted, text = ptr(), w.BOOL(), ptr()
    assert api.GetSecurityDescriptorOwner(buffer, ctypes.byref(sid), ctypes.byref(defaulted))
    raw = ctypes.string_at(sid, api.GetLengthSid(sid))
    assert api.ConvertSidToStringSidW(sid, ctypes.byref(text))
    try:
        return raw, ctypes.wstring_at(text)
    finally:
        assert not kernel.LocalFree(text)


def process_account():
    """TokenUser is a disposable fixture identity, never a designated human."""
    from ctypes import wintypes as w

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ptr = ctypes.c_void_p
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [ptr], ptr
    api.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    api.GetTokenInformation.argtypes = [
        w.HANDLE,
        ctypes.c_int,
        ptr,
        w.DWORD,
        ctypes.POINTER(w.DWORD),
    ]
    api.GetLengthSid.argtypes, api.GetLengthSid.restype = [ptr], w.DWORD
    api.ConvertSidToStringSidW.argtypes = [ptr, ctypes.POINTER(ptr)]
    token = w.HANDLE()
    assert api.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token))
    try:
        needed = w.DWORD()
        api.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(needed.value)
        assert api.GetTokenInformation(token, 1, buffer, len(buffer), ctypes.byref(needed))
        sid = ptr.from_buffer(buffer)
        raw = ctypes.string_at(sid, api.GetLengthSid(sid))
        text = ptr()
        assert api.ConvertSidToStringSidW(sid, ctypes.byref(text))
        try:
            return raw, ctypes.wstring_at(text)
        finally:
            assert not kernel.LocalFree(text)
    finally:
        assert kernel.CloseHandle(token)


def provision_fixture_acl(path, account):
    sid, text = account
    native_acl(path, text, set_owner=owner(path)[0] != sid)
    assert owner(path) == (sid, text)


@pytest.mark.parametrize("default_owner", [ACCOUNT, ADMINISTRATORS])
def test_fixture_provisions_selected_account_not_default_owner(monkeypatch, default_owner):
    module = __import__(__name__, fromlist=["owner"])
    observed = Mock(side_effect=[(default_owner, "default"), (ACCOUNT, "account")])
    setter = Mock()
    monkeypatch.setattr(module, "owner", observed)
    monkeypatch.setattr(module, "native_acl", setter)
    provision_fixture_acl("disposable", (ACCOUNT, "account"))
    setter.assert_called_once_with("disposable", "account", set_owner=default_owner != ACCOUNT)


def setup(fx, tmp_path):
    from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles

    path = tmp_path / "designation-record-v1.txt"
    path.write_bytes(b"record")
    sid, text = process_account()
    provision_fixture_acl(tmp_path, (sid, text))
    provision_fixture_acl(path, (sid, text))
    assert owner(tmp_path) == owner(path) == (sid, text)
    files = _WindowsFactFiles(str(tmp_path))
    identities = []
    for target, directory in ((str(tmp_path), True), (str(path), False)):
        handle = files._open(target, directory=directory)
        try:
            identities.append(files._check(handle, target, directory=directory)[:2])
        finally:
            files._close([handle])
    expected = SourceCustodyPolicy(*identities, sid, tuple(sorted((sid, SYSTEM))), acl(sid, SYSTEM))
    reader = _DesignationRecordSnapshots(
        trusted_root=str(tmp_path), pin_reader=fx[0], custody_policy=expected
    )
    return reader, path, text, expected


def test_native_exact_policy_live_snapshot_is_partial_not_permission(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, _, _ = setup(fx, tmp_path)
        args = fx[1]
        with fx[0]._open_facts(**args) as facts:
            with reader._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as handle:
                require(reader, handle, fx)
                with pytest.raises(OSError):
                    path.write_bytes(b"changed")
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
        assert reader._files._live is None


@pytest.mark.parametrize(
    "attack", ["broad", "unprotected", "identity", "replacement", "missing", "hardlink"]
)
def test_native_source_policy_substitution_whole_lease_denied(tmp_path, attack):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, text, expected = setup(fx, tmp_path)
        if attack == "broad":
            native_acl(path, text, suffix="(A;;FR;;;WD)")
        elif attack == "unprotected":
            native_acl(path, text, protected=False)
        elif attack == "identity":
            reader._files._policy = replace(
                expected, record_identity=(expected.record_identity[0], b"X" * 16)
            )
        elif attack in ("replacement", "missing"):
            path.unlink()
            if attack == "replacement":
                path.write_bytes(b"record")
                native_acl(path, text)
        else:
            import os

            os.link(path, tmp_path / "alias.txt")
        args = fx[1]
        with fx[0]._open_facts(**args) as facts:
            with (
                pytest.raises(PrivateFactsDenied),
                reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
            ):
                pytest.fail("substituted source became policy-valid snapshot")
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


@pytest.mark.parametrize("target", ["root", "record"])
def test_native_acl_change_after_read_then_restore_cannot_revive(tmp_path, target):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, text, _ = setup(fx, tmp_path)
        args = fx[1]
        with (
            fx[0]._open_facts(**args) as facts,
            reader._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as handle,
        ):
            require(reader, handle, fx)
            source = tmp_path if target == "root" else path
            native_acl(source, text, suffix="(A;;FR;;;WD)")
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
            native_acl(source, text)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
            with pytest.raises(WitnessLifetimeDenied):
                witness_check(fx)


@pytest.mark.parametrize(
    "failure",
    [
        "GetSecurityInfo",
        "GetSecurityDescriptorControl",
        "IsValidSecurityDescriptor",
        "IsValidAcl",
        "IsValidSid",
    ],
)
def test_native_security_api_failures_deny(tmp_path, monkeypatch, failure):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, _, _ = setup(fx, tmp_path)
        security = reader._files._security
        monkeypatch.setattr(
            security._api, failure, Mock(return_value=5 if failure == "GetSecurityInfo" else False)
        )
        args = fx[1]
        with (
            fx[0]._open_facts(**args) as facts,
            pytest.raises(PrivateFactsDenied),
            reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
        ):
            pytest.fail("native security failure allowed")


@pytest.mark.parametrize("raises", [False, True])
def test_native_descriptor_cleanup_failure_retained_until_explicit_cleanup(
    tmp_path, monkeypatch, raises
):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, _, _ = setup(fx, tmp_path)
        security = reader._files._security
        free = security._kernel.LocalFree
        args = fx[1]
        try:

            def fail_free(pointer):
                if raises:
                    raise OSError("disposable native cleanup failure")
                return pointer.value

            monkeypatch.setattr(security._kernel, "LocalFree", fail_free)
            with (
                fx[0]._open_facts(**args) as facts,
                pytest.raises(PrivateFactsDenied),
                reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
            ):
                pytest.fail("failed descriptor free allowed")
            assert security._retained
            with pytest.raises(PrivateFactsDenied), reader._files._snapshot():
                pytest.fail("retained failed descriptor ignored")
        finally:
            monkeypatch.setattr(security._kernel, "LocalFree", free)
            security._cleanup()
        assert not security._retained


def test_no_caller_policy_provider_or_public_fallback(tmp_path):
    for supplied in (True, {}, object()):
        with pytest.raises(PrivateFactsDenied):
            _CustodyDesignationRecordFiles(str(tmp_path), supplied)


def test_native_concurrent_acl_mutation_and_snapshot_owner_thread(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, path, text, _ = setup(fx, tmp_path)
        args = fx[1]
        with (
            fx[0]._open_facts(**args) as facts,
            reader._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as handle,
            ThreadPoolExecutor(max_workers=1) as executor,
        ):
            require(reader, handle, fx)
            with pytest.raises(OSError):
                executor.submit(path.write_bytes, b"changed").result(timeout=5)
            executor.submit(native_acl, path, text, suffix="(A;;FR;;;WD)").result(timeout=5)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)
            executor.submit(native_acl, path, text).result(timeout=5)
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)


def test_native_custody_source_junction_is_not_matching_identity(tmp_path):
    if not native():
        return
    target = tmp_path / "target"
    target.mkdir()
    with fixture(target) as fx:
        _, _, _, expected = setup(fx, target)
        alias = tmp_path / "alias"
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)], capture_output=True, check=False
        )
        assert result.returncode == 0
        with (
            pytest.raises(PrivateFactsDenied),
            _CustodyDesignationRecordFiles(str(alias), expected)._snapshot(),
        ):
            pytest.fail("junction became exact independent source")


def test_native_custody_snapshot_transaction_replacement_denied(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, _, _ = setup(fx, tmp_path)
        args = fx[1]
        with (
            fx[0]._open_facts(**args) as facts,
            reader._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as handle,
        ):
            require(reader, handle, fx)
            args["session"].rollback()
            args["session"].begin()
            with pytest.raises(PrivateFactsDenied):
                require(reader, handle, fx)


def test_native_denied_cleanup_retry_still_retains_ownership(tmp_path, monkeypatch):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, _, _, _ = setup(fx, tmp_path)
        security = reader._files._security
        free = security._kernel.LocalFree
        args = fx[1]
        try:
            monkeypatch.setattr(security._kernel, "LocalFree", lambda pointer: pointer.value)
            with (
                fx[0]._open_facts(**args) as facts,
                pytest.raises(PrivateFactsDenied),
                reader._open_record(lease=args["lease"], session=args["session"], pin_facts=facts),
            ):
                pytest.fail("cleanup failure allowed")
            original = tuple(security._retained)
            with pytest.raises(PrivateFactsDenied):
                security._cleanup()
            assert tuple(security._retained) == original
        finally:
            monkeypatch.setattr(security._kernel, "LocalFree", free)
            security._cleanup()
