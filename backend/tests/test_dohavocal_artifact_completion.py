from __future__ import annotations

import hashlib
import io
import json
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import backend.models  # noqa: F401
from backend.contracts.vocal_jobs import VOCAL_JOB_INPUT_SETTINGS_KEY, VOCAL_JOB_OUTPUT_ROLES
from backend.core.payload_locator import PayloadLocatorStatus, format_locator_id
from backend.db.base import Base
from backend.db.sqlite import configure_sqlite_foreign_keys
from backend.models.workspace import (
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    Job,
    JobInput,
    JobOutput,
    JobStatus,
    ModelUsage,
    MusicProject,
    PayloadLocator,
    ProcessingChain,
    ProjectAsset,
    ProviderJobBinding,
    Workspace,
)
from backend.repositories.workspace import (
    AssetRepository,
    JobRepository,
    PayloadLocatorRepository,
)
from backend.services.workspace import (
    ArtifactIngestionError,
    ArtifactIngestionErrorCode,
    ArtifactIngestionService,
    DohaVocalArtifactCompletionError,
    DohaVocalArtifactCompletionErrorCode,
    DohaVocalArtifactCompletionRequest,
    DohaVocalArtifactCompletionService,
    SqlAlchemyVocalCompletionAuthorityPort,
    TrustedPayloadSourceCandidate,
    TrustedProviderResultCandidate,
    VerifiedArtifactStreamFacts,
    VerifiedStreamArtifactIngestionRequest,
    VocalCompletionAuthorityMode,
    VocalCompletionModelFacts,
    staged_payload_from_record,
)
from backend.storage import ArtifactStorageRoots, LocalFilesystemStagingAdapter
from backend.storage.verified_payload_staging import ExpectedPayloadFacts

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def _wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(8_000)
        payload.writeframes(b"\x00\x00" * 80)
    return output.getvalue()


@dataclass(slots=True)
class _Rights:
    allowed: bool = True
    calls: int = 0
    deny_on_call: int | None = None

    def require_current(
        self,
        session: Session,
        *,
        trusted_principal: object,
        owner_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        job: Job,
        candidate: TrustedProviderResultCandidate,
        mode: VocalCompletionAuthorityMode,
    ) -> None:
        assert session.in_transaction()
        assert trusted_principal == "principal"
        assert owner_id and workspace_id and project_id and job and candidate and mode
        self.calls += 1
        if not self.allowed or self.calls == self.deny_on_call:
            raise PermissionError("C:\\private\\voice.wav bearer secret")


@dataclass(frozen=True, slots=True)
class _Graph:
    factory: sessionmaker[Session]
    service: DohaVocalArtifactCompletionService
    ingestion: ArtifactIngestionService
    staging: LocalFilesystemStagingAdapter
    rights: _Rights
    request: DohaVocalArtifactCompletionRequest
    owner_id: UUID
    project_id: UUID
    source_asset_id: UUID
    source_version_id: UUID
    selected_version_id: UUID
    locator_id: UUID
    artifact_root: object


def _graph(tmp_path, job_type: str = "voice_conversion") -> _Graph:
    engine = configure_sqlite_foreign_keys(
        create_engine(f"sqlite:///{(tmp_path / f'{job_type}.db').as_posix()}")
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    artifact_root = tmp_path / "artifacts"
    for domain in ("audio", "lm", "music", "vocal"):
        (artifact_root / domain).mkdir(parents=True)
    staging_root = tmp_path / "staging"
    staging_root.mkdir()
    (tmp_path / "publisher-staging").mkdir()
    staging = LocalFilesystemStagingAdapter(staging_root, clock=lambda: NOW)
    payload = (
        json.dumps({"pitch": [440]}, separators=(",", ":")).encode()
        if job_type == "vocal_analysis"
        else _wav()
    )
    media_type = "application/json" if job_type == "vocal_analysis" else "audio/wav"
    checksum = hashlib.sha256(payload).hexdigest()
    owner_id = uuid4()
    claim_token = uuid4()
    locator_id = uuid4()
    with factory.begin() as session:
        workspace = Workspace(owner_id=owner_id, name="Completion", lifecycle_status="active")
        session.add(workspace)
        session.flush()
        project = MusicProject(
            workspace_id=workspace.workspace_id,
            title="Vocal",
            description=None,
            lifecycle_status="active",
            created_by=owner_id,
        )
        source_asset = Asset(
            workspace_id=workspace.workspace_id,
            owner_id=owner_id,
            asset_type=AssetType.VOCAL,
            lifecycle_status="active",
        )
        session.add_all((project, source_asset))
        session.flush()
        source = AssetVersion(
            asset_id=source_asset.asset_id,
            version_number=1,
            version_origin="user_created",
            settings_snapshot={},
            created_by=owner_id,
        )
        session.add(source)
        session.flush()
        parent = AssetVersion(
            asset_id=source_asset.asset_id,
            version_number=2,
            version_origin="user_edited",
            parent_asset_version_id=source.asset_version_id,
            settings_snapshot={},
            created_by=owner_id,
        )
        session.add(parent)
        session.flush()
        source_asset.selected_asset_version_id = parent.asset_version_id
        source_artifact = Artifact(
            asset_version_id=source.asset_version_id,
            artifact_kind="audio",
            media_type="audio/wav",
            size_bytes=1,
            checksum_algorithm="sha256",
            artifact_checksum="1" * 64,
            producer_type="user",
            retention_status="active",
        )
        chain = ProcessingChain(
            name=f"chain-{uuid4()}",
            chain_version="1",
            chain_checksum=uuid4().hex * 2,
            created_by=owner_id,
        )
        session.add_all((source_artifact, chain))
        session.flush()
        session.add(
            ProjectAsset(
                project_id=project.project_id,
                asset_id=source_asset.asset_id,
                role="vocal",
                display_order=0,
            )
        )
        job_input = {
            "job_type": job_type,
            "source_asset_version_id": str(source.asset_version_id),
            "parent_asset_version_id": str(parent.asset_version_id),
            "processing_chain_id": str(chain.processing_chain_id),
        }
        job = Job(
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            job_type=job_type,
            status=JobStatus.RUNNING,
            provider_id="dohavocal",
            api_contract_version="0.2.0",
            model_manifest_id="dynamic-vocal@2",
            progress_percent=10,
            settings_snapshot={"strength": 0.5, VOCAL_JOB_INPUT_SETTINGS_KEY: job_input},
            requested_by=owner_id,
            attempt=1,
            claimed_by="worker-1",
            claim_token=claim_token,
            lease_expires_at=NOW + timedelta(hours=1),
        )
        session.add(job)
        session.flush()
        session.add(
            JobInput(
                job_id=job.job_id,
                artifact_id=source_artifact.artifact_id,
                input_role="source_vocal",
                input_order=0,
            )
        )
        binding = ProviderJobBinding(
            workspace_job_id=job.job_id,
            provider_id="dohavocal",
            provider_job_id=f"provider-{uuid4().hex}",
        )
        session.add(binding)
        session.flush()
        role = VOCAL_JOB_OUTPUT_ROLES[job_type]
        staged = staging.stage_verified(
            locator_id,
            [payload],
            expected=ExpectedPayloadFacts("sha256", checksum, len(payload), media_type),
        )
        session.add(
            PayloadLocator(
                payload_locator_id=locator_id,
                workspace_job_id=job.job_id,
                provider_job_binding_id=binding.provider_job_binding_id,
                payload_ordinal=0,
                provider_artifact_id="provider-artifact-1",
                role=role,
                source_kind="provider_subresource",
                source_id="content-1",
                artifact_kind="analysis" if job_type == "vocal_analysis" else "audio",
                expected_checksum_algorithm="sha256",
                expected_payload_checksum=checksum,
                expected_size_bytes=len(payload),
                expected_media_type=media_type,
                source_available_until=NOW + timedelta(hours=1),
                locator_expires_at=NOW + timedelta(hours=1),
                staging_status=PayloadLocatorStatus.VERIFIED_STAGED.value,
                staging_backend=staged.staging_backend,
                staging_key=staged.staging_key,
                actual_checksum_algorithm="sha256",
                actual_payload_checksum=checksum,
                actual_size_bytes=len(payload),
                actual_media_type=media_type,
                verified_at=NOW,
                lifecycle_revision=1,
            )
        )
        trusted_payload = TrustedPayloadSourceCandidate(
            provider_artifact_id="provider-artifact-1",
            role=role,
            source_kind="provider_subresource",
            source_id="content-1",
            checksum_algorithm="sha256",
            payload_checksum=checksum,
            expected_size_bytes=len(payload),
            expected_media_type=media_type,
            available_until=NOW + timedelta(hours=1),
        )
        candidate = TrustedProviderResultCandidate(
            workspace_job_id=job.job_id,
            provider_job_binding_id=binding.provider_job_binding_id,
            provider_id="dohavocal",
            provider_job_id=binding.provider_job_id,
            output_role=role,
            provider_artifact_id="provider-artifact-1",
            provider_result_artifact_id="result-1",
            provider_output_asset_version_id="provider-version-1",
            source_asset_version_id=source.asset_version_id,
            parent_asset_version_id=parent.asset_version_id,
            processing_chain_id=chain.processing_chain_id,
            model_manifest_id="dynamic-vocal@2",
            settings_snapshot={"strength": 0.5},
            artifact_kind="analysis" if job_type == "vocal_analysis" else "audio",
            media_type=media_type,
            payload_present=True,
            metadata_checksum="2" * 64,
            checksum_scope="metadata_descriptor",
            created_at=NOW,
            provider_source_artifact_id=None,
            provider_parent_artifact_id=None,
            processing_types=(job_type,),
            analysis_result={"pitch": [440]} if job_type == "vocal_analysis" else None,
            payloads=(trusted_payload,),
        )
        request = DohaVocalArtifactCompletionRequest(
            candidate=candidate,
            payload_locator_id=format_locator_id(locator_id),
            claimed_by="worker-1",
            execution_claim_token=claim_token,
            trusted_principal="principal",
            model=VocalCompletionModelFacts(
                model_id="vocal-model",
                model_version="2",
                checkpoint_version="cp-1",
                license_status="verified",
                commercial_usage_status="allowed",
            ),
        )
        values = (
            project.project_id,
            source_asset.asset_id,
            source.asset_version_id,
            parent.asset_version_id,
        )
    rights = _Rights()
    authority = SqlAlchemyVocalCompletionAuthorityPort(rights, clock=lambda: NOW)
    ingestion = ArtifactIngestionService(
        factory,
        artifact_roots=ArtifactStorageRoots.from_base_root(artifact_root),
        staging_root=(tmp_path / "publisher-staging"),
    )
    service = DohaVocalArtifactCompletionService(
        factory, staging=staging, ingestion=ingestion, authority=authority
    )
    return _Graph(
        factory,
        service,
        ingestion,
        staging,
        rights,
        request,
        owner_id,
        values[0],
        values[1],
        values[2],
        values[3],
        locator_id,
        artifact_root,
    )


@pytest.mark.parametrize(
    ("facts", "code"),
    [
        (("0" * 64, None, None), ArtifactIngestionErrorCode.CHECKSUM_MISMATCH),
        ((None, 1, None), ArtifactIngestionErrorCode.CHECKSUM_MISMATCH),
        ((None, None, "application/json"), ArtifactIngestionErrorCode.MEDIA_TYPE_MISMATCH),
    ],
)
def test_verified_stream_handoff_is_path_free_and_fails_closed(tmp_path, facts, code) -> None:
    graph = _graph(tmp_path)
    content = _wav()
    checksum, size, media_type = facts
    request = VerifiedStreamArtifactIngestionRequest(
        asset_version_id=graph.source_version_id,
        artifact_kind="audio",
        producer_type="provider",
        storage_domain="vocal",
    )
    assert not hasattr(request, "temporary_path")
    with pytest.raises(ArtifactIngestionError) as raised:
        graph.ingestion.prepare_verified_stream(
            request,
            io.BytesIO(content),
            expected_facts=VerifiedArtifactStreamFacts(
                "sha256",
                checksum or hashlib.sha256(content).hexdigest(),
                size or len(content),
                media_type or "audio/wav",
            ),
        )
    assert raised.value.code is code


@pytest.mark.parametrize(
    "job_type", ["vocal_generation", "voice_conversion", "vocal_correction", "vocal_analysis"]
)
def test_completion_output_authority_and_replay(tmp_path, job_type: str) -> None:
    graph = _graph(tmp_path, job_type)
    first = graph.service.complete(graph.request)
    replay = graph.service.complete(graph.request)
    assert replay == replace(first, replayed=True)
    with graph.factory() as session:
        job = session.get(Job, first.job_id)
        locator = session.get(PayloadLocator, graph.locator_id)
        output = session.scalar(select(JobOutput).where(JobOutput.job_id == first.job_id))
        artifact = session.get(Artifact, first.artifact_id)
        versions = session.scalars(
            select(AssetVersion).where(AssetVersion.asset_id == graph.source_asset_id)
        ).all()
        assert job.status is JobStatus.SUCCEEDED
        assert locator.staging_status == PayloadLocatorStatus.INGESTED.value
        assert locator.ingested_artifact_id == first.artifact_id
        assert output.artifact_id == first.artifact_id
        assert artifact.asset_version_id == first.asset_version_id
        assert session.scalar(select(func.count()).select_from(JobOutput)) == 1
        assert session.scalar(select(func.count()).select_from(ModelUsage)) == 1
        source_asset = session.get(Asset, graph.source_asset_id)
        assert source_asset.selected_asset_version_id == graph.selected_version_id
        if job_type == "vocal_generation":
            assert first.asset_id != graph.source_asset_id
            version = session.get(AssetVersion, first.asset_version_id)
            assert version.version_number == 1 and version.parent_asset_version_id is None
            membership = session.scalar(
                select(ProjectAsset).where(
                    ProjectAsset.project_id == graph.project_id,
                    ProjectAsset.asset_id == first.asset_id,
                )
            )
            assert membership.role == "vocal"
        elif job_type in {"voice_conversion", "vocal_correction"}:
            assert first.asset_id == graph.source_asset_id
            version = session.get(AssetVersion, first.asset_version_id)
            assert version.version_number == 3
            assert version.parent_asset_version_id == graph.selected_version_id
            assert len(versions) == 3
        else:
            assert first.asset_id == graph.source_asset_id
            assert first.asset_version_id == graph.source_version_id
            assert artifact.artifact_kind == "evaluation"
            assert len(versions) == 2


def test_replay_after_staging_cleanup_never_reopens_staging(tmp_path, monkeypatch) -> None:
    graph = _graph(tmp_path)
    staged = staged_payload_from_record(_locator(graph))
    first = graph.service.complete(graph.request)
    assert graph.staging.delete_verified(staged)
    with graph.factory.begin() as session:
        locator = session.get(PayloadLocator, graph.locator_id)
        locator.staging_status = PayloadLocatorStatus.CLEANED.value
        locator.cleanup_requested_at = NOW
        locator.cleanup_completed_at = NOW
        session.get(Asset, graph.source_asset_id).deleted_at = NOW
    monkeypatch.setattr(graph.staging, "open_verified", lambda *_: pytest.fail("staging reopened"))
    assert graph.service.complete(graph.request) == replace(first, replayed=True)


def _locator(graph: _Graph):
    from backend.repositories.workspace import PayloadLocatorRepository

    with graph.factory() as session:
        return PayloadLocatorRepository(session).get_by_locator_uuid(graph.locator_id)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("rights_after_io", DohaVocalArtifactCompletionErrorCode.RIGHTS_DENIED),
        ("claim", DohaVocalArtifactCompletionErrorCode.STALE_CLAIM),
        ("cancel", DohaVocalArtifactCompletionErrorCode.CANCELLED),
        ("locator", DohaVocalArtifactCompletionErrorCode.INVALID_AUTHORITY),
        ("revoke", DohaVocalArtifactCompletionErrorCode.INVALID_AUTHORITY),
    ],
)
def test_final_authority_failures_leave_no_partial_db_state(tmp_path, mutation, code) -> None:
    graph = _graph(tmp_path)
    if mutation == "rights_after_io":
        graph.rights.deny_on_call = 2
    else:
        with graph.factory.begin() as session:
            job = session.get(Job, graph.request.candidate.workspace_job_id)
            locator = session.get(PayloadLocator, graph.locator_id)
            if mutation == "claim":
                job.claim_token = uuid4()
            elif mutation == "cancel":
                job.cancel_requested_at = NOW
            elif mutation == "locator":
                locator.staging_status = PayloadLocatorStatus.SOURCE_BOUND.value
                locator.staging_backend = locator.staging_key = None
                locator.actual_checksum_algorithm = locator.actual_payload_checksum = None
                locator.actual_size_bytes = locator.actual_media_type = locator.verified_at = None
            else:
                locator.revoked_at = NOW
                locator.revocation_reason = "rights_revoked"
    with pytest.raises(DohaVocalArtifactCompletionError) as raised:
        graph.service.complete(graph.request)
    assert raised.value.code is code
    with graph.factory() as session:
        assert session.scalar(select(func.count()).select_from(JobOutput)) == 0
        assert session.scalar(select(func.count()).select_from(ModelUsage)) == 0
        job = session.get(Job, graph.request.candidate.workspace_job_id)
        assert job.status is JobStatus.RUNNING


@pytest.mark.parametrize(
    "mutation",
    ["workspace", "owner", "project", "result_binding", "source_binding"],
)
def test_scope_result_and_source_mismatch_fail_closed(tmp_path, mutation) -> None:
    graph = _graph(tmp_path)
    request = graph.request
    if mutation == "workspace":
        request = replace(
            request,
            candidate=replace(request.candidate, workspace_job_id=uuid4()),
        )
    elif mutation == "result_binding":
        request = replace(
            request,
            candidate=replace(request.candidate, provider_job_id="different-result"),
        )
    elif mutation == "source_binding":
        request = replace(
            request,
            candidate=replace(
                request.candidate,
                source_asset_version_id=graph.selected_version_id,
            ),
        )
    else:
        with graph.factory.begin() as session:
            if mutation == "owner":
                session.get(Asset, graph.source_asset_id).owner_id = uuid4()
            else:
                membership = session.scalar(
                    select(ProjectAsset).where(ProjectAsset.project_id == graph.project_id)
                )
                membership.deleted_at = NOW
    with pytest.raises(DohaVocalArtifactCompletionError) as raised:
        graph.service.complete(request)
    assert raised.value.code is DohaVocalArtifactCompletionErrorCode.INVALID_AUTHORITY
    with graph.factory() as session:
        assert session.scalar(select(func.count()).select_from(JobOutput)) == 0
        assert session.scalar(select(func.count()).select_from(ModelUsage)) == 0


@pytest.mark.parametrize(
    "failure_point",
    ["asset", "version", "artifact", "job_output", "model_usage", "locator"],
)
def test_transaction_stage_failure_rolls_back_and_compensates(
    tmp_path, monkeypatch, failure_point
) -> None:
    graph = _graph(tmp_path, "vocal_generation" if failure_point == "asset" else "voice_conversion")

    def fail(*_args, **_kwargs):
        raise RuntimeError("C:\\private\\voice.wav bearer secret")

    targets = {
        "asset": (AssetRepository, "add_asset"),
        "version": (AssetRepository, "add_asset_version"),
        "artifact": (graph.ingestion, "register_prepared"),
        "job_output": (JobRepository, "add_job_output"),
        "model_usage": (JobRepository, "add_model_usage"),
        "locator": (PayloadLocatorRepository, "compare_and_set"),
    }
    monkeypatch.setattr(*targets[failure_point], fail)
    with pytest.raises(DohaVocalArtifactCompletionError) as raised:
        graph.service.complete(graph.request)
    assert raised.value.code is DohaVocalArtifactCompletionErrorCode.PERSISTENCE_FAILED
    assert "private" not in str(raised.value)
    assert "secret" not in str(raised.value)
    with graph.factory() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 1
        assert session.scalar(select(func.count()).select_from(AssetVersion)) == 2
        assert session.scalar(select(func.count()).select_from(Artifact)) == 1
        assert session.scalar(select(func.count()).select_from(JobOutput)) == 0
        assert session.scalar(select(func.count()).select_from(ModelUsage)) == 0
        locator = session.get(PayloadLocator, graph.locator_id)
        assert locator.staging_status == PayloadLocatorStatus.VERIFIED_STAGED.value
        job = session.get(Job, graph.request.candidate.workspace_job_id)
        assert job.status is JobStatus.RUNNING
    assert not tuple((graph.artifact_root / "vocal").rglob("*.wav"))


def test_conflicting_replay_fails_closed_without_mutation(tmp_path) -> None:
    graph = _graph(tmp_path)
    graph.service.complete(graph.request)
    bad_payload = replace(graph.request.candidate.payloads[0], payload_checksum="f" * 64)
    candidate = replace(graph.request.candidate, payloads=(bad_payload,))
    bad = replace(graph.request, candidate=candidate)
    with pytest.raises(DohaVocalArtifactCompletionError) as raised:
        graph.service.complete(bad)
    assert raised.value.code is DohaVocalArtifactCompletionErrorCode.CONFLICT
    with graph.factory() as session:
        assert session.scalar(select(func.count()).select_from(Artifact)) == 2
        assert session.scalar(select(func.count()).select_from(JobOutput)) == 1


def test_concurrent_completion_converges_on_one_authoritative_result(tmp_path) -> None:
    graph = _graph(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: graph.service.complete(graph.request), range(2)))
    assert results[0].artifact_id == results[1].artifact_id
    assert sum(result.replayed for result in results) == 1
    with graph.factory() as session:
        assert session.scalar(select(func.count()).select_from(JobOutput)) == 1
        assert session.scalar(select(func.count()).select_from(ModelUsage)) == 1
        assert session.scalar(select(func.count()).select_from(AssetVersion)) == 3
        assert session.scalar(select(func.count()).select_from(Artifact)) == 2
