from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
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
from backend.services.workspace.artifact_ingestion_service import (
    ArtifactIngestionError,
    ArtifactIngestionService,
    TrustedAdoptedArtifactRegistrationRequest,
)
from backend.storage.artifact_publisher import (
    LocalArtifactPublisher,
    TrustedPublicationIdentity,
)
from backend.storage.artifact_resolver import APPROVED_STORAGE_DOMAINS, ArtifactStorageRoots


def test_fresh_process_adopted_registration_replays_and_rolls_back(tmp_path: Path) -> None:
    roots_path = tmp_path / "artifacts"
    staging = tmp_path / "staging"
    staging.mkdir()
    roots_path.mkdir(parents=True, exist_ok=True)
    for domain in APPROVED_STORAGE_DOMAINS:
        (roots_path / domain).mkdir(parents=True, exist_ok=True)
    roots = ArtifactStorageRoots.from_base_root(roots_path)
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    owner_id = uuid4()
    with sessions() as session, session.begin():
        asset = Asset(owner_id=owner_id, asset_type=AssetType.CANDIDATE, lifecycle_status="active")
        session.add(asset)
        session.flush()
        version = AssetVersion(
            asset_id=asset.asset_id,
            version_number=1,
            version_origin="music_director",
            settings_snapshot={},
            created_by=owner_id,
        )
        session.add(version)
        session.flush()
        version_id = version.asset_version_id

    payload = b'{"operations":[],"schema_version":1}'
    digest = hashlib.sha256(payload).hexdigest()
    job_id = uuid4()
    identity = TrustedPublicationIdentity.for_music_director_proposal(job_id, 0, digest)
    source = staging / "proposal.json"
    source.write_bytes(payload)
    LocalArtifactPublisher(roots, staging).publish_or_adopt(
        source,
        identity=identity,
        artifact_kind="manifest",
        expected_media_type="application/json",
        expected_sha256=digest,
        expected_size_bytes=len(payload),
    )
    artifact_id = uuid4()
    request = TrustedAdoptedArtifactRegistrationRequest(
        artifact_id=artifact_id,
        asset_version_id=version_id,
        identity=identity,
        artifact_kind="manifest",
        producer_type="provider",
        expected_media_type="application/json",
        expected_sha256=digest,
        expected_size_bytes=len(payload),
    )

    service = ArtifactIngestionService(sessions, artifact_roots=roots, staging_root=staging)
    with sessions() as session, session.begin():
        registered = service.register_trusted_adopted_in_session(session, request)
        assert registered.artifact_id == artifact_id
    fresh_service = ArtifactIngestionService(sessions, artifact_roots=roots, staging_root=staging)
    with sessions() as session, session.begin():
        replayed = fresh_service.register_trusted_adopted_in_session(session, request)
        assert replayed.artifact_id == artifact_id
    with sessions() as session:
        assert len(list(session.scalars(select(Artifact)))) == 1
        assert len(list(session.scalars(select(ArtifactStorageLocation)))) == 1

    rollback_id = uuid4()
    rollback_payload = b'{"operations":[{"op":"set_master_gain","value":0}],"schema_version":1}'
    rollback_digest = hashlib.sha256(rollback_payload).hexdigest()
    rollback_identity = TrustedPublicationIdentity.for_music_director_proposal(
        job_id, 1, rollback_digest
    )
    rollback_source = staging / "rollback-proposal.json"
    rollback_source.write_bytes(rollback_payload)
    rollback_publication = LocalArtifactPublisher(roots, staging).publish_or_adopt(
        rollback_source,
        identity=rollback_identity,
        artifact_kind="manifest",
        expected_media_type="application/json",
        expected_sha256=rollback_digest,
        expected_size_bytes=len(rollback_payload),
    )
    assert rollback_identity.storage_key != identity.storage_key
    with pytest.raises(RuntimeError), sessions() as session, session.begin():
        fresh_service.register_trusted_adopted_in_session(
            session,
            replace(
                request,
                artifact_id=rollback_id,
                identity=rollback_identity,
                expected_sha256=rollback_digest,
                expected_size_bytes=len(rollback_payload),
            ),
        )
        raise RuntimeError("rollback")
    with sessions() as session:
        assert session.get(Artifact, rollback_id) is None
        assert len(list(session.scalars(select(Artifact)))) == 1
        assert len(list(session.scalars(select(ArtifactStorageLocation)))) == 1
    assert rollback_publication.path.exists()


def test_adopted_registration_rejects_tamper_and_lineage_mismatch(tmp_path: Path) -> None:
    roots_path = tmp_path / "artifacts"
    staging = tmp_path / "staging"
    staging.mkdir()
    roots_path.mkdir(parents=True, exist_ok=True)
    for domain in APPROVED_STORAGE_DOMAINS:
        (roots_path / domain).mkdir(parents=True, exist_ok=True)
    roots = ArtifactStorageRoots.from_base_root(roots_path)
    engine = create_database_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    payload = b'{"operations":[1],"schema_version":1}'
    digest = hashlib.sha256(payload).hexdigest()
    identity = TrustedPublicationIdentity.for_music_director_proposal(uuid4(), 0, digest)
    source = staging / "proposal.json"
    source.write_bytes(payload)
    published = LocalArtifactPublisher(roots, staging).publish_or_adopt(
        source,
        identity=identity,
        artifact_kind="manifest",
        expected_media_type="application/json",
        expected_sha256=digest,
        expected_size_bytes=len(payload),
    )
    published.path.write_bytes(b'{"tampered":true}')
    service = ArtifactIngestionService(sessions, artifact_roots=roots, staging_root=staging)
    request = TrustedAdoptedArtifactRegistrationRequest(
        artifact_id=uuid4(),
        asset_version_id=uuid4(),
        identity=identity,
        artifact_kind="manifest",
        producer_type="provider",
        expected_media_type="application/json",
        expected_sha256=digest,
        expected_size_bytes=len(payload),
    )
    with sessions() as session, session.begin(), pytest.raises(ArtifactIngestionError):
        service.register_trusted_adopted_in_session(session, request)
