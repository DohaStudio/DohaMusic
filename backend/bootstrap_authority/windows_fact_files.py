"""Read-only Win32 stable snapshot mechanics; no provisioning/authority/secret loader."""

from __future__ import annotations

import ctypes
import ntpath
import re
import sys
from contextlib import contextmanager

from backend.bootstrap_authority.pin_facts import MAX_PIN_FACTS, PrivateFactsDenied

PIN_FACTS_FILE = "pin-comparison-facts-v1.json"


def _root_components(root: str) -> tuple[str, ...]:
    # Deliberately bounded local DOS/ASCII subset: no UNC/device/ADS/relative,
    # short-name aliases, dot segments, trailing dots/spaces or path coercion.
    if type(root) is not str or not re.fullmatch(r"[A-Za-z]:\\[^\\]+(?:\\[^\\]+)*", root):
        raise PrivateFactsDenied()
    parts = root[3:].split("\\")
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    for part in parts:
        if (
            not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
            or part in (".", "..")
            or part.endswith(".")
            or part.split(".")[0].upper() in reserved
        ):
            raise PrivateFactsDenied()
    if len(root + "\\" + PIN_FACTS_FILE) >= 260:
        raise PrivateFactsDenied()
    paths = [root[:3]]
    for part in parts:
        paths.append(ntpath.join(paths[-1], part))
    return tuple(paths)


class _WindowsFactFiles:
    """Root injected ONLY by future trusted composition; no request/env factory.

    This validates transport safety, NOT root custody/ACL/designation authenticity.
    File data is public comparison facts in a separately managed private boundary.
    All path handles remain open with no write/delete sharing through the yield.
    """

    def __init__(self, root: str) -> None:
        self._paths = _root_components(root)
        if sys.platform != "win32":
            raise PrivateFactsDenied()
        from ctypes import wintypes as w

        class Info(ctypes.Structure):
            _fields_ = [
                ("attributes", w.DWORD),
                ("created", w.FILETIME),
                ("accessed", w.FILETIME),
                ("modified", w.FILETIME),
                ("volume", w.DWORD),
                ("size_high", w.DWORD),
                ("size_low", w.DWORD),
                ("links", w.DWORD),
                ("index_high", w.DWORD),
                ("index_low", w.DWORD),
            ]

        class FileId(ctypes.Structure):
            _fields_ = [("volume", ctypes.c_ulonglong), ("identifier", ctypes.c_ubyte * 16)]

        self._info_type, self._id_type = Info, FileId
        try:
            self._api = ctypes.WinDLL("kernel32", use_last_error=True)
        except OSError:
            raise PrivateFactsDenied() from None
        signatures = {
            "CreateFileW": (
                [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE],
                w.HANDLE,
            ),
            "GetFileInformationByHandle": ([w.HANDLE, ctypes.POINTER(Info)], w.BOOL),
            "GetFileInformationByHandleEx": (
                [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD],
                w.BOOL,
            ),
            "GetFinalPathNameByHandleW": ([w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD], w.DWORD),
            "GetFileType": ([w.HANDLE], w.DWORD),
            "ReadFile": (
                [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p],
                w.BOOL,
            ),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self._api, name)
            function.argtypes, function.restype = arguments, result
        self._quarantine: list[list[int]] = []

    def _open(self, path: str, *, directory: bool) -> int:
        # OPEN_EXISTING; OPEN_REPARSE_POINT for EACH component, not just the leaf.
        handle = self._api.CreateFileW(
            path,
            0x80 if directory else 0x80000000,
            1,
            None,
            3,
            0x00200000 | (0x02000000 if directory else 0),
            None,
        )
        if handle in (None, ctypes.c_void_p(-1).value):
            raise PrivateFactsDenied()
        return handle

    def _check(self, handle: int, path: str, *, directory: bool):
        info, identity = self._info_type(), self._id_type()
        final = ctypes.create_unicode_buffer(1024)
        count = self._api.GetFinalPathNameByHandleW(handle, final, len(final), 0)
        if (
            self._api.GetFileType(handle) != 1
            or not self._api.GetFileInformationByHandle(handle, ctypes.byref(info))
            or not self._api.GetFileInformationByHandleEx(
                handle, 18, ctypes.byref(identity), ctypes.sizeof(identity)
            )
            or not 0 < count < len(final)
            or not final.value.startswith("\\\\?\\")
            or ntpath.normcase(final.value[4:]).rstrip("\\") != ntpath.normcase(path).rstrip("\\")
            or info.attributes & 0x400
            or bool(info.attributes & 0x10) != directory
            or (not directory and info.links != 1)
        ):
            raise PrivateFactsDenied()
        return (identity.volume, bytes(identity.identifier), info.size_high, info.size_low)

    def _close(self, handles: list[int]) -> None:
        while handles:
            if not self._api.CloseHandle(handles[-1]):
                raise PrivateFactsDenied()
            handles.pop()

    def _cleanup_failed_snapshots(self) -> None:
        for handles in tuple(self._quarantine):
            self._close(handles)
            self._quarantine.remove(handles)

    @contextmanager
    def _snapshot(self):
        handles, observations = [], []
        try:
            for path in self._paths:
                handle = self._open(path, directory=True)
                handles.append(handle)
                observations.append((handle, path, self._check(handle, path, directory=True)))
            path = ntpath.join(self._paths[-1], PIN_FACTS_FILE)
            handle = self._open(path, directory=False)
            handles.append(handle)
            before = self._check(handle, path, directory=False)
            size = (before[2] << 32) | before[3]
            if not 0 < size <= MAX_PIN_FACTS:
                raise PrivateFactsDenied()
            buffer, count = ctypes.create_string_buffer(size + 1), ctypes.c_ulong(0)
            if not self._api.ReadFile(handle, buffer, size + 1, ctypes.byref(count), None):
                raise PrivateFactsDenied()
            if count.value != size or before != self._check(handle, path, directory=False):
                raise PrivateFactsDenied()
            for parent_handle, parent_path, prior in observations:
                if prior[:2] != self._check(parent_handle, parent_path, directory=True)[:2]:
                    raise PrivateFactsDenied()
            yield buffer.raw[:size]
        finally:
            try:
                self._close(handles)
            except PrivateFactsDenied:
                self._quarantine.append(handles)
                raise
