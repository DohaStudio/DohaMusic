from __future__ import annotations

import hashlib
import io
import os
import wave
from dataclasses import fields
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import (
    Artifact,
    ArtifactStorageLocation,
    Asset,
    AssetType,
    AssetVersion,
)
from backend.services.workspace import (
    ArtifactAccessError,
    ArtifactAccessErrorCode,
    ArtifactApplicationService,
    ArtifactIngestionRequest,
    ArtifactIngestionService,
    ArtifactReconciliationError,
    ArtifactReconciliationIssueType,
    ArtifactReconciliationService,
)
from backend.storage.artifact_resolver import (
    APPROVED_STORAGE_DOMAINS,
    ArtifactStorageRoots,
)


class ArtifactFixture:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "artifacts"
        self.staging = tmp_path / "staging"
        self.staging.mkdir()
        for domain in APPROVED_STORAGE_DOMAINS:
            (self.root / domain).mkdir(parents=True)
        self.roots = ArtifactStorageRoots.from_base_root(self.root)
        self.engine = create_database_engine(f"sqlite:///{tmp_path / 'fixture.db'}")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, autoflush=False
        )
        self.owner_id = uuid4()
        self.asset_id, self.version_id = self._seed_lineage(self.owner_id)

    def _seed_lineage(self, owner_id: UUID) -> tuple[UUID, UUID]:
        with self.session_factory() as session, session.begin():
            asset = Asset(
                owner_id=owner_id,
                asset_type=AssetType.MUSIC,
                lifecycle_status="active",
            )
            session.add(asset)
            session.flush()
            version = AssetVersion(
                asset_id=asset.asset_id,
                version_number=1,
                version_origin="provider",
                settings_snapshot={},
                created_by=owner_id,
            )
            session.add(version)
            session.flush()
            return asset.asset_id, version.asset_version_id

    def ingest(
        self,
        payload: bytes | None = None,
        *,
        retention_status: str = "active",
        domain: str = "audio",
    ) -> UUID:
        payload = payload if payload is not None else _wav_payload()
        source = self.staging / f"{uuid4()}.wav"
        source.write_bytes(payload)
        result = ArtifactIngestionService(
            self.session_factory,
            artifact_roots=self.roots,
            staging_root=self.staging,
        ).ingest(
            ArtifactIngestionRequest(
                asset_version_id=self.version_id,
                artifact_kind="audio",
                producer_type="provider",
                storage_domain=domain,
                temporary_path=source,
            )
        )
        if retention_status != "active":
            with self.session_factory() as session, session.begin():
                artifact = session.get(Artifact, result.artifact_id)
                assert artifact is not None
                artifact.retention_status = retention_status
        return result.artifact_id

    def artifact(self, artifact_id: UUID) -> Artifact:
        with self.session_factory() as session:
            artifact = session.get(Artifact, artifact_id)
            assert artifact is not None
            session.expunge(artifact)
            return artifact

    def location(self, artifact_id: UUID) -> ArtifactStorageLocation:
        with self.session_factory() as session:
            location = session.scalar(
                select(ArtifactStorageLocation).where(
                    ArtifactStorageLocation.artifact_id == artifact_id
                )
            )
            assert location is not None
            session.expunge(location)
            return location

    def payload_path(self, artifact_id: UUID) -> Path:
        location = self.location(artifact_id)
        return self.roots.candidate_path(location.storage_domain, location.storage_key)

    def application_service(self) -> ArtifactApplicationService:
        return ArtifactApplicationService(self.session_factory, artifact_roots=self.roots)

    def reconciliation_service(self, **kwargs: object) -> ArtifactReconciliationService:
        return ArtifactReconciliationService(
            self.session_factory, artifact_roots=self.roots, **kwargs
        )


@pytest.fixture
def artifacts(tmp_path: Path) -> ArtifactFixture:
    return ArtifactFixture(tmp_path)


def _wav_payload(frames: int = 16) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(8_000)
        payload.writeframes(b"\x00\x00" * frames)
    return output.getvalue()


def _assert_access_error(
    expected: ArtifactAccessErrorCode,
    callback: object,
) -> None:
    with pytest.raises(ArtifactAccessError) as raised:
        callback()
    assert raised.value.code == expected
    assert "\\" not in str(raised.value)


def test_same_owner_metadata_returns_path_free_projection(
    artifacts: ArtifactFixture,
) -> None:
    artifact_id = artifacts.ingest()
    result = artifacts.application_service().get_artifact_for_owner(
        artifact_id, effective_owner_id=artifacts.owner_id
    )
    assert result.artifact_id == artifact_id
    assert result.asset_version_id == artifacts.version_id
    assert result.retention_status == "active"
    assert all("path" not in field.name for field in fields(result))


def test_different_owner_and_missing_artifact_are_not_found(
    artifacts: ArtifactFixture,
) -> None:
    artifact_id = artifacts.ingest()
    service = artifacts.application_service()
    for target_id, owner_id in (
        (artifact_id, uuid4()),
        (uuid4(), artifacts.owner_id),
    ):
        _assert_access_error(
            ArtifactAccessErrorCode.NOT_FOUND,
            lambda target_id=target_id, owner_id=owner_id: service.get_artifact_for_owner(
                target_id, effective_owner_id=owner_id
            ),
        )


def test_soft_deleted_asset_hides_artifact(artifacts: ArtifactFixture) -> None:
    artifact_id = artifacts.ingest()
    with artifacts.session_factory() as session, session.begin():
        asset = session.get(Asset, artifacts.asset_id)
        assert asset is not None
        from backend.models.workspace.mixins import utc_now

        asset.deleted_at = utc_now()
    _assert_access_error(
        ArtifactAccessErrorCode.NOT_FOUND,
        lambda: artifacts.application_service().get_artifact_for_owner(
            artifact_id, effective_owner_id=artifacts.owner_id
        ),
    )


@pytest.mark.parametrize(
    "retention_status",
    ["active", "quarantined", "expired", "pending_delete", "deleted"],
)
def test_metadata_retention_matrix_allows_official_states(
    artifacts: ArtifactFixture,
    retention_status: str,
) -> None:
    artifact_id = artifacts.ingest(retention_status=retention_status)
    metadata = artifacts.application_service().get_artifact_for_owner(
        artifact_id, effective_owner_id=artifacts.owner_id
    )
    assert metadata.retention_status == retention_status


def test_metadata_unknown_retention_fails_closed(artifacts: ArtifactFixture) -> None:
    artifact_id = artifacts.ingest(retention_status="unknown")
    _assert_access_error(
        ArtifactAccessErrorCode.CONTENT_UNAVAILABLE,
        lambda: artifacts.application_service().get_artifact_for_owner(
            artifact_id, effective_owner_id=artifacts.owner_id
        ),
    )


@pytest.mark.parametrize(
    ("retention_status", "expected"),
    [
        ("quarantined", ArtifactAccessErrorCode.QUARANTINED),
        ("expired", ArtifactAccessErrorCode.GONE),
        ("pending_delete", ArtifactAccessErrorCode.GONE),
        ("deleted", ArtifactAccessErrorCode.GONE),
        ("unknown", ArtifactAccessErrorCode.CONTENT_UNAVAILABLE),
    ],
)
def test_content_retention_matrix_fails_closed(
    artifacts: ArtifactFixture,
    retention_status: str,
    expected: ArtifactAccessErrorCode,
) -> None:
    artifact_id = artifacts.ingest(retention_status=retention_status)
    service = artifacts.application_service()

    def open_content() -> None:
        with service.open_content_for_owner(artifact_id, effective_owner_id=artifacts.owner_id):
            pass

    _assert_access_error(expected, open_content)


def test_active_content_full_checksum_uses_same_stream(
    artifacts: ArtifactFixture,
) -> None:
    payload = _wav_payload()
    artifact_id = artifacts.ingest(payload)
    with artifacts.application_service().open_content_for_owner(
        artifact_id, effective_owner_id=artifacts.owner_id
    ) as (handle, stream):
        assert handle.artifact_checksum == hashlib.sha256(payload).hexdigest()
        assert handle.size_bytes == len(payload)
        assert stream.read() == payload
        assert all("path" not in field.name for field in fields(handle))


@pytest.mark.parametrize("drift", ["missing", "size", "checksum"])
def test_content_integrity_gate_detects_payload_drift(
    artifacts: ArtifactFixture,
    drift: str,
) -> None:
    artifact_id = artifacts.ingest()
    payload_path = artifacts.payload_path(artifact_id)
    if drift == "missing":
        payload_path.unlink()
        expected = ArtifactAccessErrorCode.CONTENT_UNAVAILABLE
    elif drift == "size":
        payload_path.write_bytes(b"changed-size")
        expected = ArtifactAccessErrorCode.INTEGRITY_ERROR
    else:
        original = payload_path.read_bytes()
        payload_path.write_bytes(b"X" + original[1:])
        expected = ArtifactAccessErrorCode.INTEGRITY_ERROR

    def open_content() -> None:
        with artifacts.application_service().open_content_for_owner(
            artifact_id, effective_owner_id=artifacts.owner_id
        ):
            pass

    _assert_access_error(expected, open_content)


def test_content_uses_ingestion_media_type_without_re_sniffing(
    artifacts: ArtifactFixture,
) -> None:
    artifact_id = artifacts.ingest()
    with artifacts.application_service().open_content_for_owner(
        artifact_id, effective_owner_id=artifacts.owner_id
    ) as (handle, stream):
        assert handle.media_type == "audio/wav"
        assert stream.read(4) == b"RIFF"


def test_invalid_locator_is_content_unavailable(artifacts: ArtifactFixture) -> None:
    artifact_id = artifacts.ingest()
    with artifacts.session_factory() as session, session.begin():
        location = session.scalar(
            select(ArtifactStorageLocation).where(
                ArtifactStorageLocation.artifact_id == artifact_id
            )
        )
        assert location is not None
        location.storage_backend = "unsupported"

    def open_content() -> None:
        with artifacts.application_service().open_content_for_owner(
            artifact_id, effective_owner_id=artifacts.owner_id
        ):
            pass

    _assert_access_error(ArtifactAccessErrorCode.CONTENT_UNAVAILABLE, open_content)


def test_reconciliation_healthy_and_dry_run_does_not_mutate(
    artifacts: ArtifactFixture,
) -> None:
    artifact_id = artifacts.ingest()
    report = artifacts.reconciliation_service(batch_size=1).scan()
    assert report.dry_run is True
    assert report.scanned_catalog_count == 1
    assert report.scanned_file_count == 1
    assert report.healthy_count == 1
    assert report.issues == ()
    assert artifacts.artifact(artifact_id).retention_status == "active"


def test_reconciliation_rejects_destructive_mode(artifacts: ArtifactFixture) -> None:
    with pytest.raises(ArtifactReconciliationError):
        artifacts.reconciliation_service().scan(dry_run=False)


def test_reconciliation_detects_db_only_missing_payload(
    artifacts: ArtifactFixture,
) -> None:
    artifact_id = artifacts.ingest()
    artifacts.payload_path(artifact_id).unlink()
    report = artifacts.reconciliation_service().scan()
    assert report.missing_payload_count == 1
    assert report.issues[0].issue_type == ArtifactReconciliationIssueType.MISSING_PAYLOAD


def test_reconciliation_detects_filesystem_only_payload(
    artifacts: ArtifactFixture,
) -> None:
    path = artifacts.root / "audio" / "payloads" / "audio" / "aa" / "orphan.wav"
    path.parent.mkdir(parents=True)
    path.write_bytes(_wav_payload())
    report = artifacts.reconciliation_service().scan()
    assert report.unreferenced_payload_count == 1
    assert report.issues[0].storage_key == "payloads/audio/aa/orphan.wav"


@pytest.mark.parametrize("drift", ["size", "checksum"])
def test_reconciliation_detects_integrity_drift(
    artifacts: ArtifactFixture,
    drift: str,
) -> None:
    artifact_id = artifacts.ingest()
    path = artifacts.payload_path(artifact_id)
    original = path.read_bytes()
    path.write_bytes(b"different" if drift == "size" else b"X" + original[1:])
    report = artifacts.reconciliation_service().scan()
    issue_types = {issue.issue_type for issue in report.issues}
    expected = (
        ArtifactReconciliationIssueType.SIZE_MISMATCH
        if drift == "size"
        else ArtifactReconciliationIssueType.CHECKSUM_MISMATCH
    )
    assert expected in issue_types
    assert report.integrity_mismatch_count >= 1


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [("storage_backend", "unsupported"), ("storage_key", "../escape")],
)
def test_reconciliation_detects_invalid_locator(
    artifacts: ArtifactFixture,
    field_name: str,
    field_value: str,
) -> None:
    artifact_id = artifacts.ingest()
    with artifacts.session_factory() as session, session.begin():
        location = session.scalar(
            select(ArtifactStorageLocation).where(
                ArtifactStorageLocation.artifact_id == artifact_id
            )
        )
        assert location is not None
        setattr(location, field_name, field_value)
    report = artifacts.reconciliation_service().scan()
    assert report.invalid_locator_count == 1
    if field_name == "storage_key":
        assert report.issues[0].storage_key is None


def test_reconciliation_detects_old_pending_but_not_recent(
    artifacts: ArtifactFixture,
) -> None:
    pending = artifacts.root / "audio" / ".ingestion"
    pending.mkdir()
    old_file = pending / "old.pending"
    recent_file = pending / "recent.pending"
    old_file.write_bytes(b"old")
    recent_file.write_bytes(b"recent")
    now = 10_000.0
    os.utime(old_file, (now - 101, now - 101))
    os.utime(recent_file, (now - 99, now - 99))
    report = artifacts.reconciliation_service(pending_grace_seconds=100, clock=lambda: now).scan()
    assert report.pending_candidate_count == 1
    assert report.issues[0].storage_key == ".ingestion/old.pending"


def test_reconciliation_scans_multiple_domains(artifacts: ArtifactFixture) -> None:
    artifacts.ingest(domain="audio")
    artifacts.ingest(domain="vocal")
    report = artifacts.reconciliation_service(batch_size=1).scan()
    assert report.scanned_catalog_count == 2
    assert report.scanned_file_count == 2
    assert report.healthy_count == 2


def test_reconciliation_symlink_or_reparse_is_not_followed(
    artifacts: ArtifactFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = artifacts.root / "audio" / "payloads"
    namespace.mkdir()
    unsafe = namespace / "outside"
    unsafe.mkdir()
    (unsafe / "payload.wav").write_bytes(_wav_payload())
    import backend.services.workspace.artifact_reconciliation_service as module

    original = module.is_link_or_reparse
    monkeypatch.setattr(
        module,
        "is_link_or_reparse",
        lambda path: path == unsafe or original(path),
    )
    report = artifacts.reconciliation_service().scan()
    assert report.unsafe_entry_count == 1
    assert report.scanned_file_count == 1


def test_reconciliation_issue_cap_bounds_memory(artifacts: ArtifactFixture) -> None:
    for index in range(3):
        path = artifacts.root / "audio" / "payloads" / "audio" / "aa" / f"{index}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_wav_payload())
    report = artifacts.reconciliation_service(max_issues=2).scan()
    assert report.unreferenced_payload_count == 3
    assert len(report.issues) == 2
    assert report.issues_truncated is True


def test_reconciliation_never_commits_or_rolls_back(
    artifacts: ArtifactFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts.ingest()
    commits = 0
    rollbacks = 0

    def forbidden_commit(*_args: object, **_kwargs: object) -> None:
        nonlocal commits
        commits += 1

    def forbidden_rollback(*_args: object, **_kwargs: object) -> None:
        nonlocal rollbacks
        rollbacks += 1

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", forbidden_commit)
    monkeypatch.setattr("sqlalchemy.orm.Session.rollback", forbidden_rollback)
    report = artifacts.reconciliation_service().scan()
    assert report.healthy_count == 1
    assert commits == rollbacks == 0


@pytest.mark.parametrize("lineage_table", ["asset_versions", "assets"])
def test_missing_lineage_is_hidden_as_not_found(
    artifacts: ArtifactFixture,
    lineage_table: str,
) -> None:
    artifact_id = artifacts.ingest()
    with artifacts.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        if lineage_table == "asset_versions":
            connection.execute(
                text("DELETE FROM asset_versions WHERE asset_version_id = :value"),
                {"value": artifacts.version_id.hex},
            )
        else:
            connection.execute(
                text("DELETE FROM assets WHERE asset_id = :value"),
                {"value": artifacts.asset_id.hex},
            )
        connection.commit()
    _assert_access_error(
        ArtifactAccessErrorCode.NOT_FOUND,
        lambda: artifacts.application_service().get_artifact_for_owner(
            artifact_id, effective_owner_id=artifacts.owner_id
        ),
    )


def test_catalog_without_artifact_drift_is_reported(
    artifacts: ArtifactFixture,
) -> None:
    artifact_id = artifacts.ingest()
    with artifacts.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.execute(
            text("DELETE FROM artifacts WHERE artifact_id = :value"),
            {"value": artifact_id.hex},
        )
        connection.commit()
    report = artifacts.reconciliation_service().scan()
    assert report.catalog_without_artifact_count == 1
