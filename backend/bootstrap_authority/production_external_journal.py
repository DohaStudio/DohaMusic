"""Fail-closed runtime open for an already provisioned external journal.

This factory never creates a database, installs schema, initializes journal
identity, writes GENESIS, repairs history, commits a transaction, or activates
production admission.  It binds reviewed configuration to one existing SQLite
journal and supplies bounded caller-owned Session capabilities.
"""

from __future__ import annotations

import ctypes
import ntpath
import re
import sqlite3
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock, get_ident

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.pool import StaticPool

from backend.bootstrap_authority.journal_repository import (
    JournalEvent,
    JournalHead,
    JournalRepository,
    PublicKeyHistory,
)
from backend.bootstrap_authority.journal_schema_v1 import (
    SCHEMA_OBJECT_DDL,
    SCHEMA_VERSION,
)
from backend.bootstrap_authority.lifecycle_verifier import DOMAIN, SCHEMA, digest
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.production_configuration import (
    CONFIGURATION_SCHEMA,
    CONFIGURATION_VERSION,
    JOURNAL_FILE,
    PRODUCTION_PROFILE,
    ProductionDeploymentExpectations,
    parse_production_deployment_configuration,
)
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles


class ProductionExternalJournalFactoryDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PRODUCTION_EXTERNAL_JOURNAL_FACTORY_DENIED")


class ProductionExternalJournalReadiness(StrEnum):
    RUNTIME_FACTORY_READY_EXISTING_JOURNAL_REQUIRED = (
        "RUNTIME_FACTORY_READY_EXISTING_JOURNAL_REQUIRED"
    )
    EXISTING_JOURNAL_VERIFIED = "EXISTING_JOURNAL_VERIFIED"


JOURNAL_ROLE = "DEPLOYMENT_LIFECYCLE_EXTERNAL_JOURNAL"
_DESCRIPTOR_READY = (
    ProductionExternalJournalReadiness.RUNTIME_FACTORY_READY_EXISTING_JOURNAL_REQUIRED
)


@dataclass(frozen=True, slots=True, repr=False)
class _ProductionExternalJournalDescriptor:
    configuration_digest: str
    configuration_schema: str
    configuration_version: int
    configuration_profile: str
    installation_id: str
    deployment_id: str
    journal_id: str
    fixed_path: str
    fixed_filename: str
    journal_schema_version: int
    journal_event_schema: str
    journal_event_domain: bytes
    role: str
    readiness: ProductionExternalJournalReadiness

    def __post_init__(self) -> None:
        if (
            type(self.configuration_digest) is not str
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.configuration_digest)
            or self.configuration_schema != CONFIGURATION_SCHEMA
            or type(self.configuration_version) is not int
            or self.configuration_version != CONFIGURATION_VERSION
            or self.configuration_profile != PRODUCTION_PROFILE
            or type(self.installation_id) is not str
            or type(self.deployment_id) is not str
            or type(self.journal_id) is not str
            or type(self.fixed_path) is not str
            or self.fixed_filename != JOURNAL_FILE
            or ntpath.basename(self.fixed_path) != self.fixed_filename
            or self.journal_schema_version != SCHEMA_VERSION
            or self.journal_event_schema != SCHEMA
            or self.journal_event_domain != DOMAIN
            or self.role != JOURNAL_ROLE
            or self.readiness is not _DESCRIPTOR_READY
        ):
            raise ValueError("PRODUCTION_JOURNAL_DESCRIPTOR")


@dataclass(frozen=True, slots=True, repr=False)
class _VerifiedJournalSnapshot:
    head: JournalHead
    history: tuple[PublicKeyHistory, ...]
    events: tuple[JournalEvent, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _ProductionJournalSession:
    _runtime: object
    _token: object
    _repository: JournalRepository
    _session: Session
    _transaction: SessionTransaction
    _thread_id: int


def _normalized_sql(value: str) -> str:
    if type(value) is not str:
        raise ValueError("SCHEMA_SQL")
    return " ".join(value.split())


def _expected_schema_objects() -> dict[tuple[str, str], str]:
    result = {}
    for statement in SCHEMA_OBJECT_DDL:
        normalized = _normalized_sql(statement)
        match = re.match(r"CREATE (TABLE|TRIGGER) ([A-Za-z0-9_]+)\b", normalized)
        if match is None:
            raise ValueError("SCHEMA_DDL")
        kind, name = match.groups()
        result[(kind.casefold(), name)] = normalized
    return result


_EXPECTED_SCHEMA_OBJECTS = _expected_schema_objects()


def _path_key(value: str) -> str:
    return ntpath.normcase(ntpath.normpath(value.replace("/", "\\"))).rstrip("\\")


class _WindowsExistingJournal(_WindowsFactFiles):
    """Pin and repeatedly verify every path component plus the database leaf.

    The observed native identity is transport stability, not custody or
    installation authority. The retained native handles plus the pinned SQLite
    connection deny ordinary rename/delete while preserving SQLite writes;
    identity/path drift is also detected and fails the runtime closed.
    """

    _fixed_name = JOURNAL_FILE

    def __init__(self, path: str) -> None:
        if type(path) is not str or ntpath.basename(path) != JOURNAL_FILE:
            raise PrivateFactsDenied()
        super().__init__(ntpath.dirname(path))
        self._journal_path = path
        self._live: dict[int, tuple[str, bool, tuple]] | None = None

    def _open(self, path: str, *, directory: bool) -> int:
        handle = self._api.CreateFileW(
            path,
            0x80,
            3,
            None,
            3,
            0x00200000 | (0x02000000 if directory else 0),
            None,
        )
        if handle in (None, ctypes.c_void_p(-1).value):
            raise PrivateFactsDenied()
        return handle

    def require_unchanged(self) -> None:
        if self._live is None:
            raise PrivateFactsDenied()
        for handle, (path, directory, prior) in tuple(self._live.items()):
            current = self._check(handle, path, directory=directory)
            if current[:2] != prior[:2]:
                raise PrivateFactsDenied()

    @contextmanager
    def hold(self):
        if self._live is not None or self._quarantine:
            raise PrivateFactsDenied()
        handles = []
        self._live = {}
        try:
            for path in self._paths:
                handle = self._open(path, directory=True)
                handles.append(handle)
                self._live[handle] = (path, True, self._check(handle, path, directory=True))
            handle = self._open(self._journal_path, directory=False)
            handles.append(handle)
            self._live[handle] = (
                self._journal_path,
                False,
                self._check(handle, self._journal_path, directory=False),
            )
            self.require_unchanged()
            yield
            self.require_unchanged()
        finally:
            self._live = None
            try:
                self._close(handles)
            except PrivateFactsDenied:
                self._quarantine.append(handles)
                raise


def _sqlite_engine(path: str, path_lease: _WindowsExistingJournal) -> Engine:
    uri = "file:/" + path.replace("\\", "/") + "?mode=rw"

    def connect():
        path_lease.require_unchanged()
        connection = sqlite3.connect(uri, uri=True, timeout=0.0, check_same_thread=False)
        try:
            path_lease.require_unchanged()
        except Exception:
            connection.close()
            raise
        return connection

    # One pinned DBAPI connection keeps transaction-owner and reconciliation
    # reads on the same opened file even if an external rename is attempted.
    return create_engine("sqlite+pysqlite://", creator=connect, poolclass=StaticPool)


def _require_database_path(session: Session, expected_path: str) -> None:
    rows = session.execute(text("PRAGMA database_list")).all()
    main_rows = tuple(row for row in rows if row[1] == "main")
    extra_rows = tuple(row for row in rows if row[1] != "main")
    if (
        len(main_rows) != 1
        or type(main_rows[0][2]) is not str
        or _path_key(main_rows[0][2]) != _path_key(expected_path)
        or len(extra_rows) > 1
        or any(row[1] != "temp" or row[2] != "" for row in extra_rows)
    ):
        raise ProductionExternalJournalFactoryDenied()


def _require_schema(session: Session) -> None:
    versions = session.execute(text("SELECT version FROM deployment_journal_schema")).all()
    if versions != [(SCHEMA_VERSION,)]:
        raise ProductionExternalJournalFactoryDenied()
    rows = session.execute(
        text(
            "SELECT type,name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        )
    ).all()
    actual = {(row.type, row.name): _normalized_sql(row.sql) for row in rows}
    if actual != _EXPECTED_SCHEMA_OBJECTS:
        raise ProductionExternalJournalFactoryDenied()
    integrity = tuple(row[0] for row in session.execute(text("PRAGMA integrity_check")).all())
    if integrity != ("ok",):
        raise ProductionExternalJournalFactoryDenied()


def _read_verified_snapshot(
    repository: JournalRepository, *, expected_journal_id: str
) -> _VerifiedJournalSnapshot:
    head = repository.read_public_head()
    history = repository.read_public_history()
    events = repository.read_verified_events()
    after = repository.read_public_head()
    if (
        type(head) is not JournalHead
        or head != after
        or head.journal_id != expected_journal_id
        or type(head.revision) is not int
        or head.revision < 1
        or len(events) != head.revision
        or not events
        or events[0].revision != 1
        or events[0].previous_digest is not None
        or any(type(item) is not PublicKeyHistory for item in history)
        or any(
            type(item) is not JournalEvent or item.journal_id != expected_journal_id
            for item in events
        )
    ):
        raise ProductionExternalJournalFactoryDenied()
    return _VerifiedJournalSnapshot(head, history, events)


class _ProductionExternalJournalRuntime:
    readiness = ProductionExternalJournalReadiness.EXISTING_JOURNAL_VERIFIED

    def __init__(self, *, descriptor, engine, path_lease) -> None:
        if (
            type(descriptor) is not _ProductionExternalJournalDescriptor
            or not isinstance(engine, Engine)
            or type(path_lease) is not _WindowsExistingJournal
        ):
            raise ProductionExternalJournalFactoryDenied()
        self.descriptor = descriptor
        self._engine = engine
        self._path_lease = path_lease
        self._lock = RLock()
        self._sessions: dict[object, _ProductionJournalSession] = {}
        self._closed = False

    def _verify(self, session: Session) -> _VerifiedJournalSnapshot:
        self._path_lease.require_unchanged()
        _require_database_path(session, self.descriptor.fixed_path)
        _require_schema(session)
        first = _read_verified_snapshot(
            JournalRepository(session), expected_journal_id=self.descriptor.journal_id
        )
        second = _read_verified_snapshot(
            JournalRepository(session), expected_journal_id=self.descriptor.journal_id
        )
        self._path_lease.require_unchanged()
        if first != second:
            raise ProductionExternalJournalFactoryDenied()
        return second

    def _verify_available(self) -> None:
        with Session(self._engine, autoflush=False, expire_on_commit=False) as session:
            self._verify(session)

    @contextmanager
    def open_session(self):
        session = Session(self._engine, autoflush=False, expire_on_commit=False)
        transaction = None
        token = object()
        capability = None
        try:
            with self._lock:
                if self._closed or self._sessions:
                    raise ProductionExternalJournalFactoryDenied()
                transaction = session.begin()
                self._verify(session)
                capability = _ProductionJournalSession(
                    self,
                    token,
                    JournalRepository(session),
                    session,
                    transaction,
                    get_ident(),
                )
                self._sessions[token] = capability
        except Exception:
            try:
                session.close()
            except Exception:
                self._closed = True
            raise ProductionExternalJournalFactoryDenied() from None

        try:
            yield capability
        finally:
            with self._lock:
                self._sessions.pop(token, None)
            try:
                session.close()
            except Exception:
                self._closed = True
                raise ProductionExternalJournalFactoryDenied() from None

    def _require_session(self, capability) -> _ProductionJournalSession:
        try:
            if type(capability) is not _ProductionJournalSession:
                raise ProductionExternalJournalFactoryDenied()
            with self._lock:
                if (
                    self._closed
                    or self._sessions.get(capability._token) is not capability
                    or capability._runtime is not self
                    or capability._thread_id != get_ident()
                    or capability._session.get_transaction() is not capability._transaction
                    or not capability._transaction.is_active
                ):
                    raise ProductionExternalJournalFactoryDenied()
            self._path_lease.require_unchanged()
            return capability
        except ProductionExternalJournalFactoryDenied:
            raise
        except Exception:
            raise ProductionExternalJournalFactoryDenied() from None

    def verified_snapshot(self, capability) -> _VerifiedJournalSnapshot:
        try:
            capability = self._require_session(capability)
            return self._verify(capability._session)
        except ProductionExternalJournalFactoryDenied:
            raise
        except Exception:
            raise ProductionExternalJournalFactoryDenied() from None

    def _reconciliation_engine(self, capability) -> Engine:
        self._require_session(capability)
        return self._engine

    def _close(self) -> None:
        with self._lock:
            active = tuple(self._sessions.values())
            self._closed = True
            self._sessions.clear()
        failed = bool(active)
        for capability in active:
            try:
                capability._session.close()
            except Exception:
                failed = True
        try:
            self._engine.dispose()
        except Exception:
            failed = True
        if failed:
            raise ProductionExternalJournalFactoryDenied()


class ProductionExternalJournalFactory:
    readiness = ProductionExternalJournalReadiness.RUNTIME_FACTORY_READY_EXISTING_JOURNAL_REQUIRED

    @staticmethod
    def _descriptor(raw_configuration, expected):
        configuration = parse_production_deployment_configuration(
            raw_configuration, expected=expected
        )
        descriptor = _ProductionExternalJournalDescriptor(
            configuration_digest=digest(raw_configuration),
            configuration_schema=CONFIGURATION_SCHEMA,
            configuration_version=CONFIGURATION_VERSION,
            configuration_profile=PRODUCTION_PROFILE,
            installation_id=configuration.installation_id,
            deployment_id=configuration.deployment_id,
            journal_id=configuration.journal_id,
            fixed_path=configuration.external_journal_path,
            fixed_filename=JOURNAL_FILE,
            journal_schema_version=SCHEMA_VERSION,
            journal_event_schema=SCHEMA,
            journal_event_domain=DOMAIN,
            role=JOURNAL_ROLE,
            readiness=(
                ProductionExternalJournalReadiness.RUNTIME_FACTORY_READY_EXISTING_JOURNAL_REQUIRED
            ),
        )
        descriptor.__post_init__()
        return descriptor

    @contextmanager
    def open_existing(
        self,
        raw_configuration: bytes,
        *,
        expected: ProductionDeploymentExpectations,
    ):
        runtime = None
        lease_context = None
        try:
            if type(self) is not ProductionExternalJournalFactory:
                raise ValueError("FACTORY_TYPE")
            descriptor = self._descriptor(raw_configuration, expected)
            path_lease = _WindowsExistingJournal(descriptor.fixed_path)
            lease_context = path_lease.hold()
            lease_context.__enter__()
            runtime = _ProductionExternalJournalRuntime(
                descriptor=descriptor,
                engine=_sqlite_engine(descriptor.fixed_path, path_lease),
                path_lease=path_lease,
            )
            runtime._verify_available()
        except Exception:
            if runtime is not None:
                with suppress(Exception):
                    runtime._close()
            if lease_context is not None:
                with suppress(Exception):
                    lease_context.__exit__(None, None, None)
            raise ProductionExternalJournalFactoryDenied() from None

        try:
            yield runtime
        finally:
            failed = False
            try:
                runtime._close()
            except Exception:
                failed = True
            try:
                lease_context.__exit__(None, None, None)
            except Exception:
                failed = True
            if failed:
                raise ProductionExternalJournalFactoryDenied() from None
