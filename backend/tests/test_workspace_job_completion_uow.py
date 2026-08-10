"""Workspace Job Completion Unit of Work의 성공·보상·replay 계약 검증."""

from __future__ import annotations

import io
from pathlib import Path
import wave
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import (
    Artifact,
    ArtifactStorageLocation,
    Asset,
    AssetType,
    AssetVersion,
    Job,
    JobOutput,
    JobStatus,
    ModelUsage,
    ProjectAsset,
)
from backend.repositories.workspace import (
    ArtifactStorageRepository,
    AssetRepository,
    JobRepository,
)
from backend.services.workspace import (
    ArtifactIngestionError,
    ArtifactIngestionErrorCode,
    ArtifactIngestionService,
    AssetService,
    JobCompletionError,
    JobCompletionErrorCode,
    JobCompletionService,
    JobReferenceInput,
    JobService,
    ProviderOutput,
    ProviderResult,
    ProviderResultStatus,
    WorkspaceService,
)
from backend.storage.artifact_resolver import (
    APPROVED_STORAGE_DOMAINS,
    ArtifactStorageRoots,
)
from backend.storage.artifact_publisher import (
    ArtifactPublishError,
    ArtifactPublishErrorCode,
)


class CompletionFixture:
    def __init__(self, tmp_path: Path) -> None:
        self.artifact_root = tmp_path / "artifacts"
        self.staging_root = tmp_path / "staging"
        self.staging_root.mkdir()
        for domain in APPROVED_STORAGE_DOMAINS:
            (self.artifact_root / domain).mkdir(parents=True)
        self.engine = create_database_engine(f"sqlite:///{tmp_path / 'completion.db'}")
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )
        self.owner_id = uuid4()
        workspace_service = WorkspaceService(self.factory)
        self.workspace = workspace_service.create_workspace(
            owner_id=self.owner_id, name="Completion 공간"
        )
        self.project = workspace_service.create_project(
            workspace_id=self.workspace.workspace_id,
            title="Completion 프로젝트",
            created_by=self.owner_id,
        )
        self.ingestion = ArtifactIngestionService(
            self.factory,
            artifact_roots=ArtifactStorageRoots.from_base_root(self.artifact_root),
            staging_root=self.staging_root,
        )
        self.completion = JobCompletionService(
            self.factory, ingestion_service=self.ingestion
        )

    def close(self) -> None:
        assert self.engine.pool.checkedout() == 0
        self.engine.dispose()

    def create_asset(
        self, asset_type: AssetType = AssetType.LYRICS, *, owner_id: UUID | None = None
    ) -> Asset:
        return AssetService(self.factory).create_asset(
            workspace_id=self.workspace.workspace_id,
            owner_id=owner_id or self.owner_id,
            asset_type=asset_type,
        )

    def running_job(
        self,
        *,
        job_type: str = "lyrics_generation",
        inputs: tuple[JobReferenceInput, ...] = (),
        key: str | None = None,
    ) -> Job:
        service = JobService(self.factory)
        created = service.create_job_for_owner(
            effective_owner_id=self.owner_id,
            project_id=self.project.project_id,
            job_type=job_type,
            api_contract_version="1",
            settings_snapshot={"seed": 7},
            idempotency_key=key or f"create-{uuid4()}",
            inputs=inputs,
            provider_id="provider-test",
            model_manifest_id="manifest-1",
        ).aggregate.job
        return service.transition_job_for_owner(
            created.job_id,
            effective_owner_id=self.owner_id,
            status=JobStatus.RUNNING,
        )

    def write(self, name: str, payload: bytes) -> Path:
        path = self.staging_root / name
        path.write_bytes(payload)
        return path

    def success_result(
        self,
        path: Path,
        target: Asset,
        *,
        role: str = "lyrics",
        kind: str = "lyrics_text",
        capability: str = "lyrics_generation",
    ) -> ProviderResult:
        return ProviderResult(
            status=ProviderResultStatus.SUCCEEDED,
            provider_id="provider-test",
            capability=capability,
            provider_contract_version="1",
            model_manifest_id="manifest-1",
            model_id="model-test",
            model_version="1.0",
            checkpoint_version="checkpoint-1",
            license_status="reviewed",
            commercial_usage_status="allowed",
            outputs=(ProviderOutput(0, role, path, kind, target.asset_id),),
        )

    def count(self, entity) -> int:
        with self.factory() as session:
            return session.scalar(select(func.count()).select_from(entity)) or 0

    def published_files(self) -> list[Path]:
        return [path for path in self.artifact_root.rglob("*") if path.is_file()]


@pytest.fixture
def completion(tmp_path: Path):
    fixture = CompletionFixture(tmp_path)
    yield fixture
    fixture.close()


def _wav_payload() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(8_000)
        payload.writeframes(b"\x00\x00" * 16)
    return output.getvalue()


def test_single_output_completion_persists_lineage_and_succeeds(
    completion: CompletionFixture,
) -> None:
    job = completion.running_job()
    target = completion.create_asset()
    source = completion.write("lyrics.txt", "완성 가사".encode())

    result = completion.completion.complete_job_with_provider_result(
        job.job_id,
        effective_owner_id=completion.owner_id,
        provider_result=completion.success_result(source, target),
    )

    assert result.replayed is False
    assert result.aggregate.job.status is JobStatus.SUCCEEDED
    assert result.aggregate.job.progress_percent == 100
    assert len(result.aggregate.outputs) == len(result.aggregate.model_usages) == 1
    output = result.aggregate.outputs[0]
    assert output.output_role == "lyrics" and output.artifact_id is not None
    assert output.asset_version_id is None
    assert completion.count(AssetVersion) == 1
    assert completion.count(Artifact) == 1
    assert completion.count(ArtifactStorageLocation) == 1
    assert completion.count(ProjectAsset) == 0
    assert not source.exists()
    assert len(completion.published_files()) == 1


def test_completion_replay_is_idempotent_and_conflict_is_fail_closed(
    completion: CompletionFixture,
) -> None:
    job = completion.running_job()
    target = completion.create_asset()
    first = completion.write("first.txt", b"same payload")
    completion.completion.complete_job_with_provider_result(
        job.job_id,
        effective_owner_id=completion.owner_id,
        provider_result=completion.success_result(first, target),
    )
    counts = tuple(
        completion.count(entity)
        for entity in (AssetVersion, Artifact, JobOutput, ModelUsage)
    )

    replay_path = completion.write("replay.txt", b"same payload")
    replay = completion.completion.complete_job_with_provider_result(
        job.job_id,
        effective_owner_id=completion.owner_id,
        provider_result=completion.success_result(replay_path, target),
    )
    assert replay.replayed is True
    assert counts == tuple(
        completion.count(entity)
        for entity in (AssetVersion, Artifact, JobOutput, ModelUsage)
    )
    assert len(completion.published_files()) == 1

    conflict_path = completion.write("conflict.txt", b"different payload")
    with pytest.raises(JobCompletionError) as caught:
        completion.completion.complete_job_with_provider_result(
            job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=completion.success_result(conflict_path, target),
        )
    assert caught.value.completion_code is JobCompletionErrorCode.CONFLICT
    assert counts == tuple(
        completion.count(entity)
        for entity in (AssetVersion, Artifact, JobOutput, ModelUsage)
    )
    assert len(completion.published_files()) == 1


def test_cancel_marker_wins_completion_race(completion: CompletionFixture) -> None:
    job = completion.running_job()
    target = completion.create_asset()
    JobService(completion.factory).cancel_job_for_owner(
        job.job_id, effective_owner_id=completion.owner_id
    )
    source = completion.write("cancel.txt", b"discard me")

    with pytest.raises(JobCompletionError) as caught:
        completion.completion.complete_job_with_provider_result(
            job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=completion.success_result(source, target),
        )
    assert caught.value.completion_code is JobCompletionErrorCode.CANCELLED
    with completion.factory() as session:
        persisted = session.get(Job, job.job_id)
        assert persisted.status is JobStatus.CANCELLED
    assert completion.count(JobOutput) == completion.count(ModelUsage) == 0
    assert completion.published_files() == []


def test_provider_failure_is_distinct_and_creates_no_output(
    completion: CompletionFixture,
) -> None:
    job = completion.running_job()
    result = ProviderResult(
        status=ProviderResultStatus.FAILED,
        provider_id="provider-test",
        capability="lyrics_generation",
        provider_contract_version="1",
        model_manifest_id="manifest-1",
        model_id="model-test",
        model_version="1.0",
        license_status="reviewed",
        commercial_usage_status="allowed",
        error_code="PROVIDER_TIMEOUT",
        error_message="Provider execution failed.",
        error_retryable=True,
    )
    completed = completion.completion.complete_job_with_provider_result(
        job.job_id,
        effective_owner_id=completion.owner_id,
        provider_result=result,
    )
    assert completed.aggregate.job.status is JobStatus.FAILED
    assert completed.aggregate.job.error_code == "PROVIDER_TIMEOUT"
    assert completion.count(JobOutput) == completion.count(ModelUsage) == 0


@pytest.mark.parametrize(
    "failure_target",
    ["asset_version", "catalog", "job_output", "model_usage", "integrity"],
)
def test_failure_injection_rolls_back_db_and_compensates_filesystem(
    completion: CompletionFixture, monkeypatch, failure_target: str
) -> None:
    job = completion.running_job()
    target = completion.create_asset()
    source = completion.write(f"{failure_target}.txt", b"payload")
    if failure_target == "asset_version":
        monkeypatch.setattr(
            AssetRepository,
            "add_asset_version",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected")),
        )
    elif failure_target == "catalog":
        monkeypatch.setattr(
            ArtifactStorageRepository,
            "add_storage_location",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected")),
        )
    elif failure_target == "job_output":
        monkeypatch.setattr(
            JobRepository,
            "add_job_output",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected")),
        )
    elif failure_target == "model_usage":
        monkeypatch.setattr(
            JobRepository,
            "add_model_usage",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected")),
        )
    else:
        monkeypatch.setattr(
            completion.ingestion,
            "verify_registered",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                ArtifactIngestionError(ArtifactIngestionErrorCode.VERIFICATION_FAILED)
            ),
        )

    with pytest.raises(JobCompletionError):
        completion.completion.complete_job_with_provider_result(
            job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=completion.success_result(source, target),
        )
    assert completion.count(AssetVersion) == 0
    assert completion.count(Artifact) == 0
    assert completion.count(ArtifactStorageLocation) == 0
    assert completion.count(JobOutput) == completion.count(ModelUsage) == 0
    assert completion.published_files() == []
    with completion.factory() as session:
        assert session.get(Job, job.job_id).status is JobStatus.FAILED


def test_invalid_media_and_output_role_fail_without_partial_state(
    completion: CompletionFixture,
) -> None:
    target = completion.create_asset()
    media_job = completion.running_job(key="invalid-media")
    invalid_media = completion.write("invalid.txt", b"\xff")
    with pytest.raises(JobCompletionError) as media_error:
        completion.completion.complete_job_with_provider_result(
            media_job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=completion.success_result(invalid_media, target),
        )
    assert media_error.value.completion_code is JobCompletionErrorCode.INGESTION_FAILED

    role_job = completion.running_job(key="invalid-role")
    invalid_role = completion.write("role.txt", b"text")
    with pytest.raises(JobCompletionError) as role_error:
        completion.completion.complete_job_with_provider_result(
            role_job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=completion.success_result(
                invalid_role, target, role="unknown"
            ),
        )
    assert role_error.value.completion_code is JobCompletionErrorCode.INVALID_RESULT
    assert completion.count(Artifact) == completion.count(JobOutput) == 0
    assert completion.published_files() == []


def test_publish_failure_leaves_no_partial_state(
    completion: CompletionFixture, monkeypatch
) -> None:
    job = completion.running_job()
    target = completion.create_asset()
    source = completion.write("publish-failure.txt", b"payload")
    monkeypatch.setattr(
        completion.ingestion._publisher,
        "publish",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ArtifactPublishError(ArtifactPublishErrorCode.PUBLISH_FAILED)
        ),
    )

    with pytest.raises(JobCompletionError) as caught:
        completion.completion.complete_job_with_provider_result(
            job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=completion.success_result(source, target),
        )

    assert caught.value.completion_code is JobCompletionErrorCode.INGESTION_FAILED
    assert completion.count(AssetVersion) == completion.count(Artifact) == 0
    assert completion.count(JobOutput) == completion.count(ModelUsage) == 0
    assert completion.published_files() == []


def test_db_commit_failure_compensates_payload_and_leaves_safe_failure(
    completion: CompletionFixture,
) -> None:
    job = completion.running_job()
    target = completion.create_asset()
    source = completion.write("commit.txt", b"payload")
    state = {"raised": False}

    def fail_first_commit(session) -> None:
        if not state["raised"]:
            state["raised"] = True
            raise RuntimeError("injected commit failure")

    event.listen(completion.factory.class_, "before_commit", fail_first_commit)
    try:
        with pytest.raises(JobCompletionError):
            completion.completion.complete_job_with_provider_result(
                job.job_id,
                effective_owner_id=completion.owner_id,
                provider_result=completion.success_result(source, target),
            )
    finally:
        event.remove(completion.factory.class_, "before_commit", fail_first_commit)

    assert completion.count(AssetVersion) == completion.count(Artifact) == 0
    assert completion.count(JobOutput) == completion.count(ModelUsage) == 0
    assert completion.published_files() == []
    with completion.factory() as session:
        assert session.get(Job, job.job_id).status is JobStatus.FAILED


def test_multi_output_failure_is_atomic(completion: CompletionFixture) -> None:
    asset_service = AssetService(completion.factory)
    source_asset = completion.create_asset(AssetType.MUSIC)
    source_version = asset_service.create_asset_version(
        asset_id=source_asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=completion.owner_id,
    )
    source_artifact = asset_service.register_artifact(
        asset_version_id=source_version.asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=1,
        artifact_checksum="a" * 64,
        producer_type="user",
        retention_status="active",
    )
    WorkspaceService(completion.factory).attach_asset(
        project_id=completion.project.project_id,
        asset_id=source_asset.asset_id,
        display_order=0,
        role="music",
    )
    job = completion.running_job(
        job_type="stem_separation",
        inputs=(
            JobReferenceInput(
                0, artifact_id=source_artifact.artifact_id, input_role="source_audio"
            ),
        ),
    )
    vocal_target = completion.create_asset(AssetType.VOCAL)
    music_target = completion.create_asset(AssetType.STEM)
    first = completion.write("vocal.wav", _wav_payload())
    second = completion.write("broken.wav", b"not audio")
    result = ProviderResult(
        status=ProviderResultStatus.SUCCEEDED,
        provider_id="provider-test",
        capability="stem_separation",
        provider_contract_version="1",
        model_manifest_id="manifest-1",
        model_id="model-test",
        model_version="1.0",
        license_status="reviewed",
        commercial_usage_status="allowed",
        outputs=(
            ProviderOutput(0, "vocal_stem", first, "stem", vocal_target.asset_id),
            ProviderOutput(
                1, "instrumental_stem", second, "stem", music_target.asset_id
            ),
        ),
    )
    baseline_versions = completion.count(AssetVersion)
    baseline_artifacts = completion.count(Artifact)
    with pytest.raises(JobCompletionError):
        completion.completion.complete_job_with_provider_result(
            job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=result,
        )
    assert completion.count(AssetVersion) == baseline_versions
    assert completion.count(Artifact) == baseline_artifacts
    assert completion.count(JobOutput) == completion.count(ModelUsage) == 0
    assert completion.published_files() == []


def test_owner_scope_and_retry_lineage_remain_isolated(
    completion: CompletionFixture,
) -> None:
    foreign_target = completion.create_asset(owner_id=uuid4())
    job = completion.running_job(key="owner-mismatch")
    source = completion.write("foreign.txt", b"payload")
    with pytest.raises(JobCompletionError) as caught:
        completion.completion.complete_job_with_provider_result(
            job.job_id,
            effective_owner_id=completion.owner_id,
            provider_result=completion.success_result(source, foreign_target),
        )
    assert caught.value.completion_code is JobCompletionErrorCode.INVALID_RESULT

    original = completion.running_job(key="original")
    service = JobService(completion.factory)
    service.transition_job_for_owner(
        original.job_id,
        effective_owner_id=completion.owner_id,
        status=JobStatus.FAILED,
        error_code="PROVIDER_FAILED",
        error_message="Provider execution failed.",
    )
    retry = service.retry_job_for_owner(
        original.job_id,
        effective_owner_id=completion.owner_id,
        idempotency_key="retry",
    ).aggregate.job
    service.transition_job_for_owner(
        retry.job_id,
        effective_owner_id=completion.owner_id,
        status=JobStatus.RUNNING,
    )
    target = completion.create_asset()
    retry_source = completion.write("retry.txt", b"retry payload")
    completion.completion.complete_job_with_provider_result(
        retry.job_id,
        effective_owner_id=completion.owner_id,
        provider_result=completion.success_result(retry_source, target),
    )
    with completion.factory() as session:
        assert session.get(Job, original.job_id).status is JobStatus.FAILED
        assert (
            session.scalar(
                select(func.count())
                .select_from(JobOutput)
                .where(JobOutput.job_id == original.job_id)
            )
            == 0
        )
        assert session.get(Job, retry.job_id).status is JobStatus.SUCCEEDED
