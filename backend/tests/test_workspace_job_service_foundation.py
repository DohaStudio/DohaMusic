"""Workspace Job Service의 생성·상태·취소·재시도 계약 검증."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from backend.core.exceptions import (
    ApplicationValidationError,
    IdempotencyConflictError,
    InvalidStateError,
    ResourceNotFoundError,
    WorkspaceBootstrapRequiredError,
)
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.idempotency_record import IdempotencyRecord
from backend.models.workspace import (
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    Job,
    JobInput,
    JobStatus,
    MusicProject,
    WORKSPACE_ENTITY_CLASSES,
    Workspace,
)
from backend.repositories.workspace import JobRepository
from backend.services.workspace import (
    AssetService,
    CompositionService,
    JobReferenceInput,
    JobService,
    SnapshotItemInput,
    WorkspaceService,
)


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'job-service.db').as_posix()}"
    )
    tables = [entity.__table__ for entity in WORKSPACE_ENTITY_CLASSES]
    tables.append(IdempotencyRecord.__table__)
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    assert engine.pool.checkedout() == 0
    engine.dispose()


@dataclass(frozen=True)
class Graph:
    owner_id: UUID
    workspace: Workspace
    project: MusicProject
    asset: Asset
    version: AssetVersion
    artifact: Artifact


def _seed_graph(factory, *, owner_id: UUID | None = None) -> Graph:
    owner = owner_id or uuid4()
    workspace_service = WorkspaceService(factory)
    asset_service = AssetService(factory)
    workspace = workspace_service.create_workspace(owner_id=owner, name="개인 공간")
    project = workspace_service.create_project(
        workspace_id=workspace.workspace_id,
        title="프로젝트",
        created_by=owner,
    )
    asset = asset_service.create_asset(
        workspace_id=workspace.workspace_id,
        owner_id=owner,
        asset_type=AssetType.MUSIC,
    )
    version = asset_service.create_asset_version(
        asset_id=asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=owner,
    )
    artifact = asset_service.register_artifact(
        asset_version_id=version.asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=10,
        artifact_checksum="a" * 64,
        producer_type="user",
        retention_status="active",
    )
    workspace_service.attach_asset(
        project_id=project.project_id,
        asset_id=asset.asset_id,
        display_order=0,
        role="music",
    )
    return Graph(owner, workspace, project, asset, version, artifact)


def _create_music_job(service: JobService, graph: Graph, *, key: str = "create-1"):
    return service.create_job_for_owner(
        effective_owner_id=graph.owner_id,
        project_id=graph.project.project_id,
        job_type="music_generation",
        api_contract_version="1",
        settings_snapshot={"prompt": "instrumental"},
        idempotency_key=key,
        inputs=(
            JobReferenceInput(
                input_order=0,
                input_role="lyrics",
                asset_version_id=graph.version.asset_version_id,
            ),
        ),
        provider_id="planned-provider",
        model_manifest_id="manifest-1",
    )


def _count(factory, entity) -> int:
    with factory() as session:
        return session.scalar(select(func.count()).select_from(entity)) or 0


def test_create_derives_server_fields_and_replays_idempotently(session_factory) -> None:
    graph = _seed_graph(session_factory)
    service = JobService(session_factory)

    created = _create_music_job(service, graph)
    replay = _create_music_job(service, graph)

    job = created.aggregate.job
    assert created.response_status == 201
    assert replay.replayed is True
    assert replay.aggregate.job.job_id == job.job_id
    assert job.workspace_id == graph.workspace.workspace_id
    assert job.requested_by == graph.owner_id
    assert job.status is JobStatus.QUEUED
    assert job.progress_percent == Decimal(0)
    assert job.stage is None
    assert job.claim_token is None and job.cancel_requested_at is None
    assert job.attempt == 0
    assert len(created.aggregate.inputs) == 1
    assert created.aggregate.inputs[0].input_role == "lyrics"
    assert created.aggregate.model_usages == ()
    assert _count(session_factory, Job) == 1


def test_create_rejects_bootstrap_owner_type_matrix_and_conflicting_key(
    session_factory,
) -> None:
    graph = _seed_graph(session_factory)
    service = JobService(session_factory)
    with pytest.raises(WorkspaceBootstrapRequiredError):
        service.create_job_for_owner(
            effective_owner_id=uuid4(),
            project_id=graph.project.project_id,
            job_type="lyrics_generation",
            api_contract_version="1",
            settings_snapshot={},
            idempotency_key="missing-bootstrap",
        )
    with pytest.raises(ApplicationValidationError):
        service.create_job_for_owner(
            effective_owner_id=graph.owner_id,
            project_id=graph.project.project_id,
            job_type="unknown",
            api_contract_version="1",
            settings_snapshot={},
            idempotency_key="bad-type",
        )
    with pytest.raises(ApplicationValidationError):
        service.create_job_for_owner(
            effective_owner_id=graph.owner_id,
            project_id=graph.project.project_id,
            job_type="mix",
            api_contract_version="1",
            settings_snapshot={},
            idempotency_key="mix-without-snapshot",
            inputs=(),
        )
    _create_music_job(service, graph, key="same-key")
    with pytest.raises(IdempotencyConflictError):
        service.create_job_for_owner(
            effective_owner_id=graph.owner_id,
            project_id=graph.project.project_id,
            job_type="lyrics_generation",
            api_contract_version="1",
            settings_snapshot={"prompt": "different"},
            idempotency_key="same-key",
        )


def test_input_xor_role_byte_lineage_and_owner_scope(session_factory) -> None:
    graph = _seed_graph(session_factory)
    service = JobService(session_factory)
    common = dict(
        effective_owner_id=graph.owner_id,
        project_id=graph.project.project_id,
        job_type="stem_separation",
        api_contract_version="1",
        settings_snapshot={},
    )
    with pytest.raises(ApplicationValidationError):
        service.create_job_for_owner(
            **common,
            idempotency_key="xor",
            inputs=(JobReferenceInput(0, input_role="source_audio"),),
        )
    with pytest.raises(ApplicationValidationError):
        service.create_job_for_owner(
            **common,
            idempotency_key="bytes",
            inputs=(
                JobReferenceInput(
                    0,
                    asset_version_id=graph.version.asset_version_id,
                    input_role="source_audio",
                ),
            ),
        )
    other = _seed_graph(session_factory)
    with pytest.raises(ResourceNotFoundError):
        service.create_job_for_owner(
            **common,
            idempotency_key="foreign",
            inputs=(
                JobReferenceInput(
                    0,
                    artifact_id=other.artifact.artifact_id,
                    input_role="source_audio",
                ),
            ),
        )
    created = service.create_job_for_owner(
        **common,
        idempotency_key="valid-artifact",
        inputs=(
            JobReferenceInput(
                0,
                artifact_id=graph.artifact.artifact_id,
                input_role="source_audio",
            ),
        ),
    )
    assert created.aggregate.inputs[0].artifact_id == graph.artifact.artifact_id


def test_snapshot_requires_exact_version(session_factory) -> None:
    graph = _seed_graph(session_factory)
    asset_service = AssetService(session_factory)
    second_asset = asset_service.create_asset(
        workspace_id=graph.workspace.workspace_id,
        owner_id=graph.owner_id,
        asset_type=AssetType.MUSIC,
    )
    second_version = asset_service.create_asset_version(
        asset_id=second_asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=graph.owner_id,
    )
    second_artifact = asset_service.register_artifact(
        asset_version_id=second_version.asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=10,
        artifact_checksum="b" * 64,
        producer_type="user",
        retention_status="active",
    )
    WorkspaceService(session_factory).attach_asset(
        project_id=graph.project.project_id,
        asset_id=second_asset.asset_id,
        display_order=1,
        role="mix",
    )
    snapshot = (
        CompositionService(session_factory)
        .create_snapshot(
            project_id=graph.project.project_id,
            effective_owner_id=graph.owner_id,
            items=(SnapshotItemInput(graph.version.asset_version_id, "music", 0),),
            mix_settings_snapshot={},
            provider_versions={},
            model_manifest_ids={},
            idempotency_key="snapshot",
        )
        .aggregate.snapshot
    )
    with pytest.raises(ApplicationValidationError):
        JobService(session_factory).create_job_for_owner(
            effective_owner_id=graph.owner_id,
            project_id=graph.project.project_id,
            job_type="export",
            api_contract_version="1",
            settings_snapshot={},
            idempotency_key="snapshot-mismatch",
            composition_snapshot_id=snapshot.composition_snapshot_id,
            inputs=(
                JobReferenceInput(
                    0, artifact_id=second_artifact.artifact_id, input_role="mix"
                ),
            ),
        )


def test_progress_transitions_terminal_immutability_and_safe_errors(
    session_factory,
) -> None:
    graph = _seed_graph(session_factory)
    service = JobService(session_factory)
    job = _create_music_job(service, graph).aggregate.job
    running = service.transition_job_for_owner(
        job.job_id,
        effective_owner_id=graph.owner_id,
        status=JobStatus.RUNNING,
        progress_percent=Decimal("10"),
        stage="dispatch",
    )
    assert running.status is JobStatus.RUNNING and running.started_at is not None
    with pytest.raises(ApplicationValidationError):
        service.update_job_progress_for_owner(
            job.job_id,
            effective_owner_id=graph.owner_id,
            progress_percent=Decimal("9"),
        )
    with pytest.raises(ApplicationValidationError):
        service.update_job_progress_for_owner(
            job.job_id,
            effective_owner_id=graph.owner_id,
            progress_percent=Decimal("20"),
            stage="C:/secret/model.bin",
        )
    failed = service.transition_job_for_owner(
        job.job_id,
        effective_owner_id=graph.owner_id,
        status=JobStatus.FAILED,
        error_code="PROVIDER_TIMEOUT",
        error_message="처리 시간이 초과되었습니다.",
        error_retryable=True,
        error_details_id="error-ref-1",
    )
    assert failed.status is JobStatus.FAILED
    with pytest.raises(InvalidStateError):
        service.update_job_progress_for_owner(
            job.job_id,
            effective_owner_id=graph.owner_id,
            progress_percent=Decimal("30"),
        )


def test_cancel_is_state_idempotent_and_running_uses_marker(session_factory) -> None:
    graph = _seed_graph(session_factory)
    service = JobService(session_factory)
    queued = _create_music_job(service, graph, key="queued").aggregate.job
    first = service.cancel_job_for_owner(
        queued.job_id, effective_owner_id=graph.owner_id
    )
    repeated = service.cancel_job_for_owner(
        queued.job_id, effective_owner_id=graph.owner_id
    )
    assert first.job.status is JobStatus.CANCELLED
    assert first.response_status == repeated.response_status == 200

    running = _create_music_job(service, graph, key="running").aggregate.job
    service.transition_job_for_owner(
        running.job_id,
        effective_owner_id=graph.owner_id,
        status=JobStatus.RUNNING,
    )
    requested = service.cancel_job_for_owner(
        running.job_id, effective_owner_id=graph.owner_id
    )
    again = service.cancel_job_for_owner(
        running.job_id, effective_owner_id=graph.owner_id
    )
    assert requested.job.status is JobStatus.RUNNING
    assert requested.job.cancel_requested_at is not None
    assert again.response_status == 202


def test_retry_creates_new_frozen_job_and_replays_same_key(session_factory) -> None:
    graph = _seed_graph(session_factory)
    service = JobService(session_factory)
    original = _create_music_job(service, graph).aggregate.job
    service.transition_job_for_owner(
        original.job_id,
        effective_owner_id=graph.owner_id,
        status=JobStatus.RUNNING,
    )
    service.transition_job_for_owner(
        original.job_id,
        effective_owner_id=graph.owner_id,
        status=JobStatus.FAILED,
        error_code="JOB_FAILED",
        error_message="작업이 실패했습니다.",
    )
    retried = service.retry_job_for_owner(
        original.job_id,
        effective_owner_id=graph.owner_id,
        idempotency_key="retry-1",
    )
    replay = service.retry_job_for_owner(
        original.job_id,
        effective_owner_id=graph.owner_id,
        idempotency_key="retry-1",
    )
    new_job = retried.aggregate.job
    assert new_job.job_id != original.job_id
    assert new_job.retry_of_job_id == original.job_id
    assert new_job.settings_snapshot == original.settings_snapshot
    assert (
        retried.aggregate.inputs[0].asset_version_id == graph.version.asset_version_id
    )
    assert replay.aggregate.job.job_id == new_job.job_id
    assert _count(session_factory, Job) == 2


def test_owner_aggregate_hides_foreign_job_and_orders_children(session_factory) -> None:
    graph = _seed_graph(session_factory)
    service = JobService(session_factory)
    job = _create_music_job(service, graph).aggregate.job
    aggregate = service.get_job_aggregate_for_owner(
        job.job_id, effective_owner_id=graph.owner_id
    )
    assert [item.input_order for item in aggregate.inputs] == [0]
    assert aggregate.outputs == () and aggregate.model_usages == ()
    with pytest.raises(ResourceNotFoundError):
        service.get_job_aggregate_for_owner(job.job_id, effective_owner_id=uuid4())


def test_input_failure_rolls_back_job_inputs_and_idempotency(
    session_factory, monkeypatch
) -> None:
    graph = _seed_graph(session_factory)

    def fail_add_input(self, item):
        raise RuntimeError("injected rollback")

    monkeypatch.setattr(JobRepository, "add_job_input", fail_add_input)
    with pytest.raises(RuntimeError, match="injected rollback"):
        _create_music_job(JobService(session_factory), graph)
    assert _count(session_factory, Job) == 0
    assert _count(session_factory, JobInput) == 0
    assert _count(session_factory, IdempotencyRecord) == 0
