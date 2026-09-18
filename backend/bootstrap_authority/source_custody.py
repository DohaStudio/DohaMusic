"""Independent expected Win32 custody POLICY comparison, never human provenance.

No policy loader, enrollment, witness issuer or production composition. Expected
identities/ACL/SID references must come from future independently reviewed setup.
Constructing this PUBLIC policy or passing these mechanics is NOT authority.
"""

import ctypes
import struct
from contextlib import contextmanager
from dataclasses import dataclass

from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles


def _sid(value: object) -> None:
    if type(value) is not bytes or not 12 <= len(value) <= 68:
        raise PrivateFactsDenied()
    count = value[1]
    if value[0] != 1 or len(value) != 8 + 4 * count or value[2:8] != b"\x00" * 5 + b"\x05":
        raise PrivateFactsDenied()
    parts = struct.unpack("<" + "I" * count, value[8:])
    # Narrow profile: explicit account/domain or service SID, or explicit SYSTEM.
    # Never infer human designation/group membership from this binary shape.
    if not (
        (count == 5 and parts[0] == 21 and parts[-1] >= 1000)
        or (count == 6 and parts[0] == 80)
        or parts == (18,)
    ):
        raise PrivateFactsDenied()


def _identity(value: object) -> None:
    if (
        type(value) is not tuple
        or len(value) != 2
        or type(value[0]) is not int
        or not 0 < value[0] < 1 << 64
        or type(value[1]) is not bytes
        or len(value[1]) != 16
        or value[1] == b"\x00" * 16
    ):
        raise PrivateFactsDenied()


@dataclass(frozen=True, slots=True, repr=False)
class SourceCustodyPolicy:
    """Public conditions only. No OS SID, descriptor or file identity is a proof."""

    root_identity: tuple[int, bytes]
    record_identity: tuple[int, bytes]
    owner_sid: bytes
    allowed_sids: tuple[bytes, ...]
    dacl: bytes

    def __post_init__(self):
        _identity(self.root_identity)
        _identity(self.record_identity)
        _sid(self.owner_sid)
        if type(self.allowed_sids) is not tuple or not 0 < len(self.allowed_sids) <= 16:
            raise PrivateFactsDenied()
        for sid in self.allowed_sids:
            _sid(sid)
        if (
            self.allowed_sids != tuple(sorted(set(self.allowed_sids)))
            or self.owner_sid not in self.allowed_sids
        ):
            raise PrivateFactsDenied()
        raw = self.dacl
        if type(raw) is not bytes or not 8 <= len(raw) <= 4096:
            raise PrivateFactsDenied()
        revision, reserved, size, count, reserved2 = struct.unpack("<BBHHH", raw[:8])
        if revision != 2 or reserved or reserved2 or size != len(raw) or not 0 < count <= 16:
            raise PrivateFactsDenied()
        offset, seen = 8, []
        for _ in range(count):
            if offset + 8 > len(raw):
                raise PrivateFactsDenied()
            kind, flags, length, mask = struct.unpack("<BBHI", raw[offset : offset + 8])
            if (
                kind != 0
                or flags
                or length < 20
                or offset + length > len(raw)
                or not mask
                or mask & ~0x1F01FF
            ):
                raise PrivateFactsDenied()
            sid = raw[offset + 8 : offset + length]
            _sid(sid)
            if sid not in self.allowed_sids or sid in seen:
                raise PrivateFactsDenied()
            seen.append(sid)
            offset += length
        if offset != len(raw) or set(seen) != set(self.allowed_sids):
            raise PrivateFactsDenied()


class _SecurityDescriptors:
    def __init__(self):
        from ctypes import wintypes as w

        try:
            self._api = ctypes.WinDLL("advapi32", use_last_error=True)
            self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        except OSError:
            raise PrivateFactsDenied() from None
        ptr = ctypes.c_void_p
        signatures = {
            "GetSecurityInfo": (
                [
                    w.HANDLE,
                    ctypes.c_int,
                    w.DWORD,
                    ctypes.POINTER(ptr),
                    ptr,
                    ctypes.POINTER(ptr),
                    ptr,
                    ctypes.POINTER(ptr),
                ],
                w.DWORD,
            ),
            "GetSecurityDescriptorControl": (
                [ptr, ctypes.POINTER(w.WORD), ctypes.POINTER(w.DWORD)],
                w.BOOL,
            ),
            "IsValidSecurityDescriptor": ([ptr], w.BOOL),
            "IsValidAcl": ([ptr], w.BOOL),
            "IsValidSid": ([ptr], w.BOOL),
            "GetLengthSid": ([ptr], w.DWORD),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self._api, name)
            function.argtypes, function.restype = args, result
        self._kernel.LocalFree.argtypes, self._kernel.LocalFree.restype = [ptr], ptr
        self._retained: list[ctypes.c_void_p] = []

    def _cleanup(self):
        for pointer in tuple(self._retained):
            self._free(pointer)
            self._retained.remove(pointer)

    def _free(self, pointer):
        try:
            if self._kernel.LocalFree(pointer):
                raise PrivateFactsDenied()
        except OSError:
            raise PrivateFactsDenied() from None

    def _require(self, handle, policy):
        from ctypes import wintypes as w

        owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        try:
            if self._retained or self._api.GetSecurityInfo(
                handle,
                1,
                5,
                ctypes.byref(owner),
                None,
                ctypes.byref(dacl),
                None,
                ctypes.byref(descriptor),
            ):
                raise PrivateFactsDenied()
            control, revision = w.WORD(), w.DWORD()
            if (
                not descriptor.value
                or not owner.value
                or not dacl.value
                or not self._api.IsValidSecurityDescriptor(descriptor)
                or not self._api.GetSecurityDescriptorControl(
                    descriptor, ctypes.byref(control), ctypes.byref(revision)
                )
                or revision.value != 1
                or control.value & 0x1004 != 0x1004
                or control.value & 9
                or not self._api.IsValidSid(owner)
                or not self._api.IsValidAcl(dacl)
            ):
                raise PrivateFactsDenied()
            length = self._api.GetLengthSid(owner)
            acl_size = struct.unpack("<H", ctypes.string_at(dacl.value + 2, 2))[0]
            if not 12 <= length <= 68 or not 8 <= acl_size <= 4096:
                raise PrivateFactsDenied()
            if (
                ctypes.string_at(owner, length) != policy.owner_sid
                or ctypes.string_at(dacl, acl_size) != policy.dacl
            ):
                raise PrivateFactsDenied()
        finally:
            if descriptor.value:
                # Retain ownership BEFORE any native call can fail or raise.
                self._retained.append(descriptor)
                self._free(descriptor)
                self._retained.remove(descriptor)


class _CustodyDesignationRecordFiles(_WindowsFactFiles):
    _fixed_name = "designation-record-v1.txt"
    _read_control = True

    def __init__(self, root: str, policy: SourceCustodyPolicy):
        if type(policy) is not SourceCustodyPolicy:
            raise PrivateFactsDenied()
        policy.__post_init__()
        super().__init__(root)
        self._policy = policy
        self._security = _SecurityDescriptors()
        self._live: dict[int, tuple] | None = None
        self._invalid = False

    def _check(self, handle, path, *, directory):
        identity = super()._check(handle, path, directory=directory)
        if not directory or path == self._paths[-1]:
            expected = self._policy.root_identity if directory else self._policy.record_identity
            if identity[:2] != expected:
                raise PrivateFactsDenied()
            self._security._require(handle, self._policy)
            if self._live is not None:
                prior = self._live.get(handle)
                value = (path, directory, identity)
                if prior is not None and prior != value:
                    raise PrivateFactsDenied()
                self._live[handle] = value
        return identity

    def _require_unchanged(self):
        if self._invalid or self._live is None or len(self._live) != 2:
            raise PrivateFactsDenied()
        try:
            for handle, (path, directory, prior) in tuple(self._live.items()):
                if self._check(handle, path, directory=directory) != prior:
                    raise PrivateFactsDenied()
        except (PrivateFactsDenied, OSError):
            self._invalid = True
            raise PrivateFactsDenied() from None

    @contextmanager
    def _snapshot(self):
        if self._live is not None or self._security._retained:
            raise PrivateFactsDenied()
        self._live, self._invalid = {}, False
        try:
            with super()._snapshot() as raw:
                self._require_unchanged()
                yield raw
        finally:
            self._invalid = True
            self._live = None
