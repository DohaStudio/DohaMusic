"""Internal Windows ceremony exclusion mechanics; NEVER admission authority.

Trusted future adapters must independently establish installation identity and the
COMPLETE authoritative scope manifest before using this component. Public UUIDs
and kernel object names do not prove either. No production factory/port wiring.
All cooperating readers/writers must use this protocol; no protection against
privileged code, hostile namespace squatting or non-cooperating writers claimed.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import sys
from dataclasses import dataclass
from threading import RLock, get_native_id

from sqlalchemy.orm import Session, SessionTransaction

from backend.bootstrap_authority.witness_lifetime import (
    _MINT,
    WitnessLifetimeDenied,
    _Handle,
    _ProviderWitnessLifetime,
    _require_scope,
)


class CeremonySerializationDenied(RuntimeError):
    def __init__(self, *, cleanup: _OwnedMutex | None = None) -> None:
        self._cleanup = cleanup
        super().__init__("DEPLOYMENT_CEREMONY_SERIALIZATION_DENIED")


@dataclass(slots=True, repr=False)
class _OwnedMutex:
    handle: int
    owned: bool


class _KernelMutexes:
    """Non-inheritable Global mutex handles, thread-owned, zero-timeout waits."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise CeremonySerializationDenied()
        from ctypes import wintypes

        try:
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        except OSError:
            raise CeremonySerializationDenied() from None
        self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateMutexW.restype = wintypes.HANDLE
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.ReleaseMutex.argtypes = [wintypes.HANDLE]
        self.api.ReleaseMutex.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL

    def acquire(self, name: str) -> _OwnedMutex:
        handle = self.api.CreateMutexW(None, False, name)
        if not handle:
            raise CeremonySerializationDenied()
        result = self.api.WaitForSingleObject(handle, 0)
        mutex = _OwnedMutex(handle, result in (0, 0x80))
        if result == 0:
            return mutex
        # WAIT_ABANDONED grants ownership, but is NOT clean ceremony success.
        # Release our acquired ownership before denying and force fresh evidence.
        # Caller owns cleanup, including failed CloseHandle, without losing the
        # native handle or falsely claiming release. Safe error text contains none.
        raise CeremonySerializationDenied(cleanup=mutex)

    def release(self, mutex: _OwnedMutex) -> None:
        if mutex.owned:
            if not self.api.ReleaseMutex(mutex.handle):
                raise CeremonySerializationDenied()
            mutex.owned = False
        if not self.api.CloseHandle(mutex.handle):
            raise CeremonySerializationDenied()


# Win32 mutexes allow recursive acquisition by the owning THREAD, even through
# another provider instance. Reject that before calling the OS. Strong token refs
# avoid equality/hash/id-reuse spoofing; this is NOT the cross-process primitive.
_RESERVATIONS_LOCK = RLock()
_RESERVATIONS: dict[str, object] = {}


def _names(scopes: object) -> tuple[str, ...]:
    try:
        if type(scopes) is not tuple or not 0 < len(scopes) <= 4096:
            raise CeremonySerializationDenied()
        for scope in scopes:
            _require_scope(scope)
        if scopes != tuple(sorted(set(scopes))):
            raise CeremonySerializationDenied()
    except WitnessLifetimeDenied:
        raise CeremonySerializationDenied() from None
    # Fixed domain, canonical fixed-length UUID tuples; no filenames/paths used.
    return tuple(
        "Global\\DohaMusicCeremonyV1_"
        + hashlib.sha256(
            ("DohaMusicCeremonyV1\x00" + "\x00".join(scope)).encode("ascii")
        ).hexdigest()
        for scope in scopes
    )


@dataclass(slots=True, repr=False)
class _LeaseRecord:
    scopes: tuple[tuple[str, str, str], ...]
    names: tuple[str, ...]
    handles: list[_OwnedMutex]
    reservation: object
    pid: int
    thread: int
    session: Session
    transaction: SessionTransaction
    invalid: bool = False


class _WindowsCeremonySerialization:
    """Provider-internal exclusion, not Provisioning/Currentness/AdmissionPort.

    Caller starts its root transaction BEFORE acquiring and ends it BEFORE release.
    No SQL/flush/commit/rollback/retry. Inactive transactions invalidate witnesses
    but do not silently unlock: caller must release on the original owning thread.
    Busy/unsupported/abandoned/access-denied all fail closed, without local fallback.
    """

    def __init__(self, lifetime: _ProviderWitnessLifetime) -> None:
        if type(lifetime) is not _ProviderWitnessLifetime:
            raise CeremonySerializationDenied()
        self._kernel = _KernelMutexes()
        self._lifetime = lifetime
        self._leases: dict[_Handle, _LeaseRecord] = {}
        self._failed_acquisitions: list[_LeaseRecord] = []
        self._lock = RLock()

    def _acquire(self, *, scopes: tuple[tuple[str, str, str], ...], session: Session) -> object:
        names = _names(scopes)
        try:
            transaction = self._lifetime._root_transaction(session)
        except WitnessLifetimeDenied:
            raise CeremonySerializationDenied() from None
        reservation = object()
        with _RESERVATIONS_LOCK:
            if any(name in _RESERVATIONS for name in names):
                raise CeremonySerializationDenied()
            for name in names:
                _RESERVATIONS[name] = reservation
        handles = []
        try:
            for name in names:
                handles.append(self._kernel.acquire(name))
        except CeremonySerializationDenied as failure:
            if failure._cleanup is not None:
                handles.append(failure._cleanup)
            try:
                while handles:
                    self._kernel.release(handles[-1])
                    handles.pop()
            except CeremonySerializationDenied:
                # No token/attempt was issued. Retain cleanup ownership and ALL
                # reservations so same-thread native recursion cannot bypass it.
                with self._lock:
                    self._failed_acquisitions.append(
                        _LeaseRecord(
                            scopes,
                            names,
                            handles,
                            reservation,
                            os.getpid(),
                            get_native_id(),
                            session,
                            transaction,
                            invalid=True,
                        )
                    )
                raise
            self._unreserve(names, reservation)
            raise
        lease = _Handle(_MINT)
        with self._lock:
            self._leases[lease] = _LeaseRecord(
                scopes,
                names,
                handles,
                reservation,
                os.getpid(),
                get_native_id(),
                session,
                transaction,
            )
        return lease

    def _cleanup_failed_acquisitions(self) -> None:
        """Explicit cleanup only, not acquisition retry/admission. Original owner only."""
        with self._lock:
            for record in tuple(self._failed_acquisitions):
                if record.pid != os.getpid() or record.thread != get_native_id():
                    raise CeremonySerializationDenied()
                while record.handles:
                    self._kernel.release(record.handles[-1])
                    record.handles.pop()
                self._unreserve(record.names, record.reservation)
                self._failed_acquisitions.remove(record)

    @staticmethod
    def _unreserve(names: tuple[str, ...], reservation: object) -> None:
        with _RESERVATIONS_LOCK:
            for name in names:
                if _RESERVATIONS.get(name) is reservation:
                    del _RESERVATIONS[name]

    def _lookup(self, lease: object) -> _LeaseRecord:
        if type(lease) is not _Handle or lease not in self._leases:
            raise CeremonySerializationDenied()
        record = self._leases[lease]
        if record.pid != os.getpid() or record.thread != get_native_id():
            raise CeremonySerializationDenied()
        return record

    def _require_live(
        self, lease: object, *, session: Session, scopes: tuple[tuple[str, str, str], ...]
    ) -> None:
        with self._lock:
            record = self._lookup(lease)
            try:
                _names(scopes)
                transaction = self._lifetime._root_transaction(session)
                if (
                    record.invalid
                    or session is not record.session
                    or transaction is not record.transaction
                    or scopes != record.scopes
                ):
                    raise CeremonySerializationDenied()
            except (WitnessLifetimeDenied, CeremonySerializationDenied):
                record.invalid = True
                self._lifetime._release_lease(lease)
                raise CeremonySerializationDenied() from None

    def _release(self, lease: object) -> None:
        with self._lock:
            record = self._lookup(lease)
            record.invalid = True
            self._lifetime._release_lease(lease)
            if record.transaction.is_active:
                raise CeremonySerializationDenied()
            # Keep failed release tracked/reserved. Never pretend cleanup succeeded
            # or allow recursive acquire; close failures may require process exit.
            while record.handles:
                self._kernel.release(record.handles[-1])
                record.handles.pop()
            self._unreserve(record.names, record.reservation)
            del self._leases[lease]
