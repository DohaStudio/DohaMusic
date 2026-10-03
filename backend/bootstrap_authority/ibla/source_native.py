"""Fixed IBLA roles over existing Windows mechanics; no provisioning or writers."""

import ctypes
import hashlib
import os
from contextlib import contextmanager
from threading import get_native_id

from backend.bootstrap_authority.contracts import require_uuid
from backend.bootstrap_authority.ibla.contracts import IblaDenied
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.production_external_journal import _WindowsExistingJournal
from backend.bootstrap_authority.source_custody import (
    SourceCustodyPolicy,
    _CustodyDesignationRecordFiles,
    _SecurityDescriptors,
)
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.bootstrap_authority.windows_serialization import (
    _RESERVATIONS,
    _RESERVATIONS_LOCK,
    CeremonySerializationDenied,
    _KernelMutexes,
)


class _AnchorFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-commissioning-anchor-v1.json"


class _ConfirmationFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-initializer-confirmation-v1.json"


class _DesignationFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-designation-original-v1.txt"


class _CeremonyFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-ceremony-original-v1.txt"


class _MappingFiles(_CustodyDesignationRecordFiles):
    _fixed_name = "ibla-commissioning-mapping-v1.json"


class _DatabaseFiles(_WindowsExistingJournal):
    """Reuse held DB mechanics, adding independently pinned native custody.

    SQLite leaf permits WRITE sharing, never DELETE, as ADR-106 requires.
    Governance text roles retain the stricter no-WRITE/no-DELETE sharing profile.
    """

    _fixed_name = "ibla-ledger-v1.sqlite3"

    def __init__(self, root, policy):
        if type(policy) is not SourceCustodyPolicy:
            raise PrivateFactsDenied()
        policy.__post_init__()
        _WindowsFactFiles.__init__(self, root)
        import ntpath

        self._journal_path = ntpath.join(root, self._fixed_name)
        self._policy, self._security, self._live = policy, _SecurityDescriptors(), None
        self._invalid = False
        from ctypes import wintypes as w

        self._api.SetFilePointerEx.argtypes = [
            w.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            w.DWORD,
        ]
        self._api.SetFilePointerEx.restype = w.BOOL

    def _open(self, path, *, directory):
        handle = self._api.CreateFileW(
            path,
            0x80 | 0x20000 | (0 if directory else 0x80000000),
            3,
            None,
            3,
            0x00200000 | (0x02000000 if directory else 0),
            None,
        )
        if handle in (None, ctypes.c_void_p(-1).value):
            raise PrivateFactsDenied()
        return handle

    def _check(self, handle, path, *, directory):
        identity = _WindowsFactFiles._check(self, handle, path, directory=directory)
        if not directory or path == self._paths[-1]:
            expected = self._policy.root_identity if directory else self._policy.record_identity
            if identity[:2] != expected:
                raise PrivateFactsDenied()
            self._security._require(handle, self._policy)
        if not directory:
            # Reject WAL/unknown stores BEFORE SQLite can create -wal/-shm sidecars
            # even with mode=ro. Same original held handle, bounded header read.
            if not self._api.SetFilePointerEx(handle, 0, None, 0):
                raise PrivateFactsDenied()
            header, count = ctypes.create_string_buffer(100), ctypes.c_ulong(0)
            if (
                not self._api.ReadFile(handle, header, 100, ctypes.byref(count), None)
                or count.value != 100
                or header.raw[:16] != b"SQLite format 3\x00"
                or header.raw[18:20] != b"\x01\x01"
            ):
                raise PrivateFactsDenied()
        return identity

    def require_unchanged(self):
        if self._invalid or self._security._retained:
            raise PrivateFactsDenied()
        try:
            super().require_unchanged()
        except Exception:
            self._invalid = True
            raise PrivateFactsDenied() from None


class _CheckpointFiles(_DatabaseFiles):
    _fixed_name = "ibla-checkpoint-v1.sqlite3"


class _DomainLease:
    """Original native thread owns cleanup; uncertainty retains mutex/reservation."""

    def __init__(self, domain):
        if type(domain) is not str:
            raise IblaDenied()
        require_uuid(domain)
        self._name = (
            "Global\\DohaMusic.IblaDomainV1_" + hashlib.sha256(domain.encode("ascii")).hexdigest()
        )
        self._owner = (os.getpid(), get_native_id())
        self._token, self._mutex, self._active = object(), None, False
        self._kernel = _KernelMutexes()

    def require_live(self):
        if (
            not self._active
            or self._mutex is None
            or not self._mutex.owned
            or self._owner != (os.getpid(), get_native_id())
        ):
            raise IblaDenied()
        with _RESERVATIONS_LOCK:
            if _RESERVATIONS.get(self._name) is not self._token:
                raise IblaDenied()

    def _cleanup(self):
        self._active = False
        if self._owner != (os.getpid(), get_native_id()):
            raise IblaDenied()
        if self._mutex is not None:
            self._kernel.release(self._mutex)
            self._mutex = None
        with _RESERVATIONS_LOCK:
            if _RESERVATIONS.get(self._name) is self._token:
                del _RESERVATIONS[self._name]

    @contextmanager
    def hold(self):
        with _RESERVATIONS_LOCK:
            if self._name in _RESERVATIONS:
                raise IblaDenied()
            _RESERVATIONS[self._name] = self._token
        try:
            try:
                self._mutex = self._kernel.acquire(self._name)
            except CeremonySerializationDenied as error:
                self._mutex = error._cleanup
                raise IblaDenied() from None
            self._active = True
            self.require_live()
            yield self
            self.require_live()
        finally:
            try:
                self._cleanup()
            except Exception:
                # Provider retains this lease object; no uncertain resource is forgotten.
                raise IblaDenied() from None
