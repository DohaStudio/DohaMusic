from __future__ import annotations

import hashlib
import io
import os
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import Settings
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import (
    Artifact,
    ArtifactStorageLocation,
    Asset,
    AssetType,
    AssetVersion,
)
from backend.repositories.workspace import (
    ArtifactStorageRepository,
    AssetRepository,
)
from backend.services.workspace.artifact_ingestion_service import (
    ArtifactIngestionError,
    ArtifactIngestionErrorCode,
    ArtifactIngestionRequest,
    ArtifactIngestionService,
    IngestedArtifact,
    OrphanCandidate,
)
from backend.storage.artifact_resolver import (
    APPROVED_STORAGE_DOMAINS,
    ArtifactStorageError,
    ArtifactStorageErrorCode,
    ArtifactStorageResolver,
    ArtifactStorageRoots,
)


class IngestionFixture:
    def __init__(self, tmp_path: Path) -> None:
        self.artifact_root = tmp_path / "artifacts"
        self.staging_root = tmp_path / "staging"
        self.staging_root.mkdir()
        for domain in APPROVED_STORAGE_DOMAINS:
            (self.artifact_root / domain).mkdir(parents=True)
        self.engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        self.asset_version_id = self._seed_asset_version()
        self.orphans: list[OrphanCandidate] = []

    def _seed_asset_version(self) -> UUID:
        with self.session_factory() as session, session.begin():
            asset = Asset(
                owner_id=uuid4(),
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
                created_by=asset.owner_id,
            )
            session.add(version)
            session.flush()
            return version.asset_version_id

    def service(
        self,
        *,
        artifact_id: UUID | None = None,
    ) -> ArtifactIngestionService:
        return ArtifactIngestionService(
            self.session_factory,
            artifact_roots=ArtifactStorageRoots.from_base_root(self.artifact_root),
            staging_root=self.staging_root,
            orphan_reporter=self.orphans.append,
            artifact_id_factory=(lambda: artifact_id) if artifact_id else uuid4,
        )

    def request(
        self,
        path: Path,
        *,
        artifact_kind: str = "audio",
        storage_domain: str = "audio",
        producer_type: str = "provider",
        expected_media_type: str | None = None,
        expected_sha256: str | None = None,
    ) -> ArtifactIngestionRequest:
        return ArtifactIngestionRequest(
            asset_version_id=self.asset_version_id,
            artifact_kind=artifact_kind,
            producer_type=producer_type,
            producer_id="provider-test",
            run_id="run-test",
            storage_domain=storage_domain,
            temporary_path=path,
            expected_media_type=expected_media_type,
            expected_sha256=expected_sha256,
            original_filename=path.name,
        )

    def write(self, name: str, payload: bytes) -> Path:
        path = self.staging_root / name
        path.write_bytes(payload)
        return path

    def rows(self) -> tuple[list[Artifact], list[ArtifactStorageLocation]]:
        with self.session_factory() as session:
            return (
                list(session.scalars(select(Artifact))),
                list(session.scalars(select(ArtifactStorageLocation))),
            )


@pytest.fixture
def ingestion(tmp_path: Path) -> IngestionFixture:
    return IngestionFixture(tmp_path)


def _wav_payload() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(8_000)
        payload.writeframes(b"\x00\x00" * 16)
    return output.getvalue()


def _flac_payload() -> bytes:
    streaminfo = bytearray(34)
    streaminfo[0:2] = (16).to_bytes(2, "big")
    streaminfo[2:4] = (16).to_bytes(2, "big")
    streaminfo[10:18] = ((8_000 << 44) | 16).to_bytes(8, "big")
    return b"fLaC" + b"\x80\x00\x00\x22" + bytes(streaminfo) + b"\xff\xf8"


def _mp3_payload() -> bytes:
    return b"ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90\x64\x00\x00"


def test_ingest_wav_round_trip_uses_authoritative_metadata(
    ingestion: IngestionFixture,
) -> None:
    payload = _wav_payload()
    source = ingestion.write("misleading.mp3", payload)

    result = ingestion.service().ingest(
        ingestion.request(
            source,
            expected_media_type="audio/wav",
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )
    )

    assert isinstance(result, IngestedArtifact)
    assert result.artifact_checksum == hashlib.sha256(payload).hexdigest()
    assert result.size_bytes == len(payload)
    assert result.media_type == "audio/wav"
    assert result.duration_us == 2_000
    assert result.staging_cleanup_pending is False
    assert not source.exists()
    artifacts, locations = ingestion.rows()
    assert len(artifacts) == len(locations) == 1
    assert artifacts[0].retention_status == "active"
    assert artifacts[0].checksum_algorithm == "sha256"
    assert artifacts[0].duration_us == 2_000
    assert locations[0].storage_key.endswith(f"{result.artifact_id}.wav")
    assert not locations[0].storage_key.startswith("audio/")

    with ingestion.session_factory() as session:
        resolver = ArtifactStorageResolver(
            ArtifactStorageRepository(session),
            ArtifactStorageRoots.from_base_root(ingestion.artifact_root),
        )
        with resolver.open_payload(result.artifact_id) as (_, stream):
            assert stream.read() == payload


@pytest.mark.parametrize(
    (
        "artifact_kind",
        "storage_domain",
        "payload",
        "media_type",
        "extension",
        "duration_us",
    ),
    [
        ("lyrics_text", "lm", "가사".encode(), "text/plain", "txt", None),
        ("manifest", "lm", b'{"version":1}', "application/json", "json", None),
        ("evaluation", "audio", b'{"score":0.9}', "application/json", "json", None),
        ("snapshot", "music", b'{"items":[]}', "application/json", "json", None),
        ("audio", "audio", _flac_payload(), "audio/flac", "flac", 2_000),
        ("stem", "vocal", _mp3_payload(), "audio/mpeg", "mp3", None),
    ],
)
def test_supported_kind_media_matrix(
    ingestion: IngestionFixture,
    artifact_kind: str,
    storage_domain: str,
    payload: bytes,
    media_type: str,
    extension: str,
    duration_us: int | None,
) -> None:
    source = ingestion.write(f"input.{extension}", payload)
    result = ingestion.service().ingest(
        ingestion.request(
            source,
            artifact_kind=artifact_kind,
            storage_domain=storage_domain,
        )
    )
    assert result.media_type == media_type
    assert result.duration_us == duration_us
    _, locations = ingestion.rows()
    assert locations[0].storage_key.endswith(f".{extension}")
    if artifact_kind == "snapshot":
        assert locations[0].storage_key.startswith("snapshots/")


@pytest.mark.parametrize("artifact_kind", ["model", "checkpoint", "unknown"])
def test_unvalidated_kinds_fail_closed(
    ingestion: IngestionFixture, artifact_kind: str
) -> None:
    source = ingestion.write("payload.bin", b"payload")
    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(
            ingestion.request(source, artifact_kind=artifact_kind, storage_domain="lm")
        )
    assert caught.value.code is ArtifactIngestionErrorCode.INVALID_KIND
    assert source.exists()
    assert ingestion.rows() == ([], [])


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("storage_domain", "unknown", ArtifactIngestionErrorCode.INVALID_DOMAIN),
        ("producer_type", "anonymous", ArtifactIngestionErrorCode.INVALID_PRODUCER),
        ("artifact_kind", "audio", ArtifactIngestionErrorCode.INVALID_KIND),
    ],
)
def test_request_allowlists_fail_closed(
    ingestion: IngestionFixture,
    field: str,
    value: str,
    code: ArtifactIngestionErrorCode,
) -> None:
    source = ingestion.write("payload.txt", b"text")
    values = {
        "artifact_kind": "lyrics_text",
        "storage_domain": "lm",
        "producer_type": "provider",
    }
    values[field] = value
    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(ingestion.request(source, **values))
    assert caught.value.code is code


def test_missing_asset_version_does_not_touch_payload(
    ingestion: IngestionFixture,
) -> None:
    source = ingestion.write("input.wav", _wav_payload())
    request = ingestion.request(source)
    request = replace(request, asset_version_id=uuid4())
    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(request)
    assert caught.value.code is ArtifactIngestionErrorCode.VERSION_NOT_FOUND
    assert source.exists()
    assert ingestion.rows() == ([], [])


@pytest.mark.parametrize("case", ["missing", "directory", "relative", "escape"])
def test_staging_boundary_rejects_invalid_inputs(
    ingestion: IngestionFixture, tmp_path: Path, case: str
) -> None:
    if case == "missing":
        source = ingestion.staging_root / "missing.wav"
    elif case == "directory":
        source = ingestion.staging_root / "directory"
        source.mkdir()
    elif case == "relative":
        source = Path("relative.wav")
    else:
        source = tmp_path / "outside.wav"
        source.write_bytes(_wav_payload())

    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(ingestion.request(source))
    assert caught.value.code is ArtifactIngestionErrorCode.INVALID_STAGING_PAYLOAD
    assert ingestion.rows() == ([], [])


def test_staging_symlink_is_rejected(
    ingestion: IngestionFixture, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.wav"
    outside.write_bytes(_wav_payload())
    link = ingestion.staging_root / "link.wav"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("현재 Windows 권한에서 실제 symlink fixture를 만들 수 없습니다.")
    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(ingestion.request(link))
    assert caught.value.code is ArtifactIngestionErrorCode.INVALID_STAGING_PAYLOAD


def test_staging_reparse_detection_fails_closed_when_os_fixture_is_unavailable(
    ingestion: IngestionFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backend.storage.artifact_publisher as module

    source = ingestion.write("input.wav", _wav_payload())

    def reject_reparse(_root: Path, _candidate: Path) -> None:
        raise ArtifactStorageError(ArtifactStorageErrorCode.STORAGE_ESCAPE)

    monkeypatch.setattr(module, "assert_safe_local_path", reject_reparse)
    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(ingestion.request(source))
    assert caught.value.code is ArtifactIngestionErrorCode.INVALID_STAGING_PAYLOAD


@pytest.mark.parametrize(
    ("artifact_kind", "payload"),
    [
        ("audio", b"<html>not audio</html>"),
        ("audio", b"RIFFbroken-WAVE"),
        ("lyrics_text", b"\xff\xfe"),
        ("manifest", b'{"broken":'),
    ],
)
def test_invalid_media_is_rejected_without_registration(
    ingestion: IngestionFixture, artifact_kind: str, payload: bytes
) -> None:
    source = ingestion.write("misleading.wav", payload)
    domain = "lm" if artifact_kind in {"lyrics_text", "manifest"} else "audio"
    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(
            ingestion.request(
                source, artifact_kind=artifact_kind, storage_domain=domain
            )
        )
    assert caught.value.code is ArtifactIngestionErrorCode.MEDIA_VALIDATION_FAILED
    assert source.exists()
    assert ingestion.rows() == ([], [])


@pytest.mark.parametrize(
    ("expected_media_type", "expected_sha256", "code"),
    [
        ("audio/mpeg", None, ArtifactIngestionErrorCode.MEDIA_TYPE_MISMATCH),
        (None, "0" * 64, ArtifactIngestionErrorCode.CHECKSUM_MISMATCH),
    ],
)
def test_hints_are_comparison_only(
    ingestion: IngestionFixture,
    expected_media_type: str | None,
    expected_sha256: str | None,
    code: ArtifactIngestionErrorCode,
) -> None:
    source = ingestion.write("input.wav", _wav_payload())
    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(
            ingestion.request(
                source,
                expected_media_type=expected_media_type,
                expected_sha256=expected_sha256,
            )
        )
    assert caught.value.code is code
    assert source.exists()
    assert ingestion.rows() == ([], [])


def test_publish_collision_never_clobbers_existing_file(
    ingestion: IngestionFixture,
) -> None:
    artifact_id = UUID("12345678-1234-5678-1234-567812345678")
    existing = (
        ingestion.artifact_root
        / "audio"
        / "payloads"
        / "audio"
        / artifact_id.hex[:2]
        / f"{artifact_id}.wav"
    )
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")
    source = ingestion.write("input.wav", _wav_payload())

    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service(artifact_id=artifact_id).ingest(ingestion.request(source))
    assert caught.value.code is ArtifactIngestionErrorCode.PUBLISH_COLLISION
    assert existing.read_bytes() == b"existing"
    assert source.exists()
    assert ingestion.rows() == ([], [])


def test_concurrent_same_target_never_clobbers_payload(
    ingestion: IngestionFixture,
) -> None:
    artifact_id = UUID("87654321-4321-8765-4321-876543218765")
    first = ingestion.write("first.wav", _wav_payload())
    second = ingestion.write("second.wav", _wav_payload())

    def ingest(path: Path) -> IngestedArtifact | ArtifactIngestionErrorCode:
        try:
            return ingestion.service(artifact_id=artifact_id).ingest(
                ingestion.request(path)
            )
        except ArtifactIngestionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(ingest, (first, second)))

    assert sum(isinstance(item, IngestedArtifact) for item in results) == 1
    assert any(
        item
        in {
            ArtifactIngestionErrorCode.PUBLISH_COLLISION,
            ArtifactIngestionErrorCode.REGISTRATION_FAILED,
        }
        for item in results
        if isinstance(item, ArtifactIngestionErrorCode)
    )
    artifacts, locations = ingestion.rows()
    assert len(artifacts) == len(locations) == 1
    final_path = (
        ingestion.artifact_root
        / "audio"
        / Path(locations[0].storage_key.replace("/", os.sep))
    )
    assert final_path.read_bytes() == _wav_payload()


@pytest.mark.parametrize("failure", ["artifact", "catalog", "commit"])
def test_database_failures_rollback_rows_and_compensate_file(
    ingestion: IngestionFixture, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    source = ingestion.write("input.wav", _wav_payload())
    if failure == "artifact":
        monkeypatch.setattr(
            AssetRepository,
            "add_artifact",
            lambda *_: (_ for _ in ()).throw(SQLAlchemyError("artifact")),
        )
    elif failure == "catalog":
        monkeypatch.setattr(
            ArtifactStorageRepository,
            "add_storage_location",
            lambda *_: (_ for _ in ()).throw(SQLAlchemyError("catalog")),
        )
    else:

        def fail_commit(_session: Session) -> None:
            raise SQLAlchemyError("commit")

        event.listen(ingestion.session_factory.class_, "before_commit", fail_commit)

    try:
        with pytest.raises(ArtifactIngestionError) as caught:
            ingestion.service().ingest(ingestion.request(source))
    finally:
        if failure == "commit":
            event.remove(ingestion.session_factory.class_, "before_commit", fail_commit)
    assert caught.value.code is ArtifactIngestionErrorCode.REGISTRATION_FAILED
    assert source.exists()
    assert ingestion.rows() == ([], [])
    assert list(ingestion.artifact_root.rglob("*.wav")) == []


def test_cleanup_failure_emits_path_free_orphan_signal(
    ingestion: IngestionFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backend.storage.artifact_publisher as module

    source = ingestion.write("input.wav", _wav_payload())
    original = module._unlink_if_identity_matches

    def fail_final_cleanup(path: Path, identity: tuple[int, int]) -> bool:
        if path.suffix == ".wav":
            return False
        return original(path, identity)

    monkeypatch.setattr(module, "_unlink_if_identity_matches", fail_final_cleanup)
    monkeypatch.setattr(
        ArtifactStorageRepository,
        "add_storage_location",
        lambda *_: (_ for _ in ()).throw(SQLAlchemyError("catalog")),
    )

    with pytest.raises(ArtifactIngestionError) as caught:
        ingestion.service().ingest(ingestion.request(source))
    assert caught.value.orphan_candidate is not None
    assert ingestion.orphans == [caught.value.orphan_candidate]
    assert ingestion.orphans[0].storage_key is not None
    assert "\\" not in str(ingestion.orphans[0])


def test_staging_cleanup_failure_returns_success_with_reconciliation_signal(
    ingestion: IngestionFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backend.storage.artifact_publisher as module

    source = ingestion.write("input.wav", _wav_payload())
    original = module._unlink_if_identity_matches

    def fail_staging_cleanup(path: Path, identity: tuple[int, int]) -> bool:
        if path == source:
            return False
        return original(path, identity)

    monkeypatch.setattr(module, "_unlink_if_identity_matches", fail_staging_cleanup)
    result = ingestion.service().ingest(ingestion.request(source))
    assert result.staging_cleanup_pending is True
    assert source.exists()
    assert ingestion.orphans[0].category == "staging_payload"


def test_duplicate_checksum_preserves_distinct_lineage_artifacts(
    ingestion: IngestionFixture,
) -> None:
    payload = _wav_payload()
    first = ingestion.service().ingest(
        ingestion.request(ingestion.write("first.wav", payload))
    )
    second = ingestion.service().ingest(
        ingestion.request(ingestion.write("second.wav", payload))
    )
    assert first.artifact_id != second.artifact_id
    assert first.artifact_checksum == second.artifact_checksum
    artifacts, locations = ingestion.rows()
    assert len(artifacts) == len(locations) == 2


def test_large_text_hashing_uses_chunked_copy(ingestion: IngestionFixture) -> None:
    payload = ("가" * 700_000).encode()
    source = ingestion.write("large.txt", payload)
    result = ingestion.service().ingest(
        ingestion.request(source, artifact_kind="lyrics_text", storage_domain="lm")
    )
    assert result.size_bytes == len(payload)
    assert result.artifact_checksum == hashlib.sha256(payload).hexdigest()


def test_configuration_is_fail_closed_and_roots_must_not_overlap(
    ingestion: IngestionFixture,
) -> None:
    with pytest.raises(ArtifactIngestionError) as missing:
        ArtifactIngestionService(
            ingestion.session_factory,
            artifact_roots=ArtifactStorageRoots.from_base_root(ingestion.artifact_root),
            staging_root=None,
        )
    assert missing.value.code is ArtifactIngestionErrorCode.CONFIGURATION_ERROR

    with pytest.raises(ArtifactIngestionError) as overlap:
        ArtifactIngestionService(
            ingestion.session_factory,
            artifact_roots=ArtifactStorageRoots.from_base_root(ingestion.artifact_root),
            staging_root=ingestion.artifact_root / "audio",
        )
    assert overlap.value.code is ArtifactIngestionErrorCode.CONFIGURATION_ERROR


def test_environment_staging_root_is_optional_and_not_defaulted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOHA_ARTIFACT_STAGING_ROOT", raising=False)
    assert Settings.from_environment().artifact_staging_root is None
    monkeypatch.setenv("DOHA_ARTIFACT_STAGING_ROOT", "D:/safe-staging")
    assert Settings.from_environment().artifact_staging_root == Path("D:/safe-staging")


def test_internal_contract_does_not_accept_authoritative_location_or_size() -> None:
    request_fields = {field.name for field in fields(ArtifactIngestionRequest)}
    result_fields = {field.name for field in fields(IngestedArtifact)}
    assert (
        not {
            "artifact_id",
            "storage_key",
            "final_path",
            "size_bytes",
            "artifact_checksum",
        }
        & request_fields
    )
    assert "path" not in result_fields
