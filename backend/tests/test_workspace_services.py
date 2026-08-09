"""Workspace Application Service transaction과 domain 계약 검증."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session, object_session, sessionmaker

from backend.core.exceptions import (
    ApplicationValidationError,
    InvalidStateError,
    ResourceConflictError,
)
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.pipeline_job import PipelineJob
from backend.models.idempotency_record import IdempotencyRecord
from backend.models.workspace import (
    Approval,
    Artifact,
    Asset,
    AssetRelation,
    AssetType,
    AssetVersion,
    Comment,
    CompositionSnapshot,
    Favorite,
    Job,
    JobInput,
    JobOutput,
    JobStatus,
    MusicProject,
    ProcessingChain,
    ProcessingStep,
    ProjectAsset,
    RecordingEnrollment,
    SnapshotItem,
    Tag,
    WORKSPACE_ENTITY_CLASSES,
    Workspace,
)
from backend.repositories.workspace import CompositionRepository, JobRepository
from backend.services.workspace import (
    AssetService,
    CollaborationService,
    CompositionService,
    JobReferenceInput,
    JobReferenceOutput,
    JobService,
    ModelUsageInput,
    ProcessingStepInput,
    SnapshotItemInput,
    WorkspaceService,
)


class TrackingSession(Session):
    commits = 0
    rollbacks = 0


@event.listens_for(TrackingSession, "after_commit")
def _count_commit(session: TrackingSession) -> None:
    TrackingSession.commits += 1


@event.listens_for(TrackingSession, "after_rollback")
def _count_rollback(session: TrackingSession) -> None:
    TrackingSession.rollbacks += 1


@pytest.fixture
def service_factory(tmp_path: Path):
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'workspace-services.db').as_posix()}"
    )
    tables = [entity.__table__ for entity in WORKSPACE_ENTITY_CLASSES]
    tables.append(IdempotencyRecord.__table__)
    Base.metadata.create_all(engine, tables=tables)
    factory = sessionmaker(
        bind=engine,
        class_=TrackingSession,
        autoflush=False,
        expire_on_commit=False,
    )
    TrackingSession.commits = 0
    TrackingSession.rollbacks = 0
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


def _seed_graph(service_factory, *, asset_type: AssetType = AssetType.MUSIC) -> Graph:
    owner_id = uuid4()
    workspace = WorkspaceService(service_factory).create_workspace(
        owner_id=owner_id, name=" 개인 음악 공간 "
    )
    project = WorkspaceService(service_factory).create_project(
        workspace_id=workspace.workspace_id,
        title=" 첫 번째 곡 ",
        created_by=owner_id,
    )
    asset = AssetService(service_factory).create_asset(
        workspace_id=workspace.workspace_id,
        owner_id=owner_id,
        asset_type=asset_type,
    )
    version = AssetService(service_factory).create_asset_version(
        asset_id=asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=owner_id,
    )
    return Graph(owner_id, workspace, project, asset, version)


def _count(factory, entity_type) -> int:
    with factory() as session:
        return session.scalar(select(func.count()).select_from(entity_type)) or 0


def test_service_transaction_commits_once_and_returns_detached_entity(
    service_factory,
) -> None:
    service = WorkspaceService(service_factory)
    before = TrackingSession.commits

    workspace = service.create_workspace(owner_id=uuid4(), name=" Workspace ")

    assert TrackingSession.commits - before == 1
    assert workspace.name == "Workspace"
    assert object_session(workspace) is None
    assert (
        service.get_workspace(workspace.workspace_id).workspace_id
        == workspace.workspace_id
    )


def test_workspace_project_validation_and_project_asset_restore(
    service_factory,
) -> None:
    graph = _seed_graph(service_factory)
    service = WorkspaceService(service_factory)

    with pytest.raises(ResourceConflictError):
        service.create_workspace(owner_id=graph.owner_id, name="개인 음악 공간")
    with pytest.raises(ApplicationValidationError):
        service.rename_workspace(graph.workspace.workspace_id, "   ")

    attached = service.attach_asset(
        project_id=graph.project.project_id,
        asset_id=graph.asset.asset_id,
        role=" music ",
        display_order=1,
    )
    service.detach_asset(
        project_id=graph.project.project_id, asset_id=graph.asset.asset_id
    )
    restored = service.attach_asset(
        project_id=graph.project.project_id,
        asset_id=graph.asset.asset_id,
        role="selected",
        display_order=0,
    )

    assert restored.project_asset_id == attached.project_asset_id
    assert restored.deleted_at is None
    assert restored.display_order == 0
    assert restored.role == "selected"
    assert _count(service_factory, ProjectAsset) == 1


def test_cross_workspace_asset_attach_is_rejected(service_factory) -> None:
    first = _seed_graph(service_factory)
    other_owner = uuid4()
    other_workspace = WorkspaceService(service_factory).create_workspace(
        owner_id=other_owner, name="다른 공간"
    )
    other_project = WorkspaceService(service_factory).create_project(
        workspace_id=other_workspace.workspace_id,
        title="다른 곡",
        created_by=other_owner,
    )

    with pytest.raises(ApplicationValidationError):
        WorkspaceService(service_factory).attach_asset(
            project_id=other_project.project_id,
            asset_id=first.asset.asset_id,
            display_order=0,
        )
    assert _count(service_factory, ProjectAsset) == 0


def test_asset_version_artifact_and_relation_contracts(service_factory) -> None:
    graph = _seed_graph(service_factory)
    service = AssetService(service_factory)
    second = service.create_asset_version(
        asset_id=graph.asset.asset_id,
        parent_asset_version_id=graph.version.asset_version_id,
        version_origin="user_edited",
        settings_snapshot={"tempo": 120},
        created_by=graph.owner_id,
    )
    artifact = service.register_artifact(
        asset_version_id=second.asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=0,
        artifact_checksum="a" * 64,
        producer_type="workspace",
        retention_status="active",
    )

    assert second.version_number == 2
    assert (
        service.get_latest_asset_version(graph.asset.asset_id).asset_version_id
        == second.asset_version_id
    )
    assert artifact.artifact_checksum == "a" * 64
    assert "update_asset_version" not in dir(service)
    assert not hasattr(Artifact, "artifact_uri")
    assert not any("path" in column.key for column in inspect(Artifact).columns)
    with pytest.raises(ResourceConflictError):
        service.create_asset_version(
            asset_id=graph.asset.asset_id,
            version_number=2,
            version_origin="user_edited",
            settings_snapshot={},
            created_by=graph.owner_id,
        )
    with pytest.raises(ApplicationValidationError):
        service.register_artifact(
            asset_version_id=second.asset_version_id,
            artifact_kind="audio",
            media_type="audio/wav",
            size_bytes=1,
            artifact_checksum="not-a-checksum",
            producer_type="workspace",
            retention_status="active",
        )
    with pytest.raises(ApplicationValidationError):
        service.create_asset_relation(
            relation_type="derived_from",
            source_asset_id=graph.asset.asset_id,
            target_asset_id=graph.asset.asset_id,
        )


def test_asset_relation_duplicate_is_conflict(service_factory) -> None:
    graph = _seed_graph(service_factory)
    target = AssetService(service_factory).create_asset(
        workspace_id=graph.workspace.workspace_id,
        owner_id=graph.owner_id,
        asset_type=AssetType.STEM,
    )
    service = AssetService(service_factory)
    first = service.create_asset_relation(
        relation_type="derived_from",
        source_asset_id=graph.asset.asset_id,
        target_asset_id=target.asset_id,
    )
    with pytest.raises(ResourceConflictError):
        service.create_asset_relation(
            relation_type="derived_from",
            source_asset_id=graph.asset.asset_id,
            target_asset_id=target.asset_id,
        )
    assert first.relation_id is not None
    assert _count(service_factory, AssetRelation) == 1


def test_snapshot_creation_is_exact_and_atomic(service_factory, monkeypatch) -> None:
    graph = _seed_graph(service_factory)
    service = CompositionService(service_factory)
    WorkspaceService(service_factory).attach_asset(
        project_id=graph.project.project_id,
        asset_id=graph.asset.asset_id,
        display_order=0,
        role="music",
    )
    original = CompositionRepository.add_snapshot_item
    calls = 0

    def fail_second(repository, item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected failure")
        return original(repository, item)

    monkeypatch.setattr(CompositionRepository, "add_snapshot_item", fail_second)
    with pytest.raises(RuntimeError, match="injected failure"):
        service.create_snapshot(
            project_id=graph.project.project_id,
            effective_owner_id=graph.owner_id,
            items=[
                SnapshotItemInput(graph.version.asset_version_id, "music", 0),
                SnapshotItemInput(graph.version.asset_version_id, "vocal", 1),
            ],
            mix_settings_snapshot={},
            provider_versions={},
            model_manifest_ids={},
            idempotency_key="snapshot-rollback",
        )

    assert _count(service_factory, CompositionSnapshot) == 0
    assert _count(service_factory, SnapshotItem) == 0
    assert TrackingSession.rollbacks >= 1


def test_snapshot_and_processing_chain_success(service_factory) -> None:
    graph = _seed_graph(service_factory)
    service = CompositionService(service_factory)
    WorkspaceService(service_factory).attach_asset(
        project_id=graph.project.project_id,
        asset_id=graph.asset.asset_id,
        display_order=0,
        role="music",
    )
    chain = service.create_processing_chain(
        name="mix",
        chain_version="1",
        chain_checksum="chain-1",
        created_by=graph.owner_id,
        steps=[ProcessingStepInput(1, "normalize", {"peak": -1})],
    )
    result = service.create_snapshot(
        project_id=graph.project.project_id,
        effective_owner_id=graph.owner_id,
        processing_chain_id=chain.processing_chain_id,
        items=[SnapshotItemInput(graph.version.asset_version_id, "music", 0)],
        mix_settings_snapshot={"gain": 0},
        provider_versions={},
        model_manifest_ids={},
        idempotency_key="snapshot-success",
    )

    assert result.aggregate.snapshot.processing_chain_id == chain.processing_chain_id
    assert result.aggregate.snapshot.snapshot_version == 1
    assert result.aggregate.snapshot.created_by == graph.owner_id
    assert "update_snapshot" not in dir(service)
    assert _count(service_factory, ProcessingChain) == 1
    assert _count(service_factory, ProcessingStep) == 1
    assert _count(service_factory, SnapshotItem) == 1


def test_job_creation_rollback_and_pipeline_separation(
    service_factory, monkeypatch
) -> None:
    graph = _seed_graph(service_factory)
    service = JobService(service_factory)
    original = JobRepository.add_job_input
    calls = 0

    def fail_second(repository, item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected failure")
        return original(repository, item)

    monkeypatch.setattr(JobRepository, "add_job_input", fail_second)
    with pytest.raises(RuntimeError, match="injected failure"):
        service.create_job(
            project_id=graph.project.project_id,
            job_type="mix",
            api_contract_version="0.1.0",
            settings_snapshot={},
            requested_by=graph.owner_id,
            inputs=[
                JobReferenceInput(0, asset_version_id=graph.version.asset_version_id),
                JobReferenceInput(1, asset_version_id=graph.version.asset_version_id),
            ],
        )

    assert _count(service_factory, Job) == 0
    assert _count(service_factory, JobInput) == 0
    assert Job.__tablename__ != PipelineJob.__tablename__


def test_job_state_transition_outputs_and_model_usage(service_factory) -> None:
    graph = _seed_graph(service_factory)
    service = JobService(service_factory)
    job = service.create_job(
        project_id=graph.project.project_id,
        job_type="mix",
        api_contract_version="0.1.0",
        settings_snapshot={},
        requested_by=graph.owner_id,
        inputs=[JobReferenceInput(0, asset_version_id=graph.version.asset_version_id)],
        model_usages=[
            ModelUsageInput(
                provider_id="workspace",
                model_manifest_id="manifest-1",
                model_id="mixer",
                model_version="1",
                api_contract_version="0.1.0",
                license_status="reviewed",
                commercial_usage_status="allowed",
            )
        ],
    )
    running = service.update_job_status(job.job_id, JobStatus.RUNNING)
    completed = service.complete_job_with_outputs(
        job.job_id,
        [JobReferenceOutput(0, asset_version_id=graph.version.asset_version_id)],
    )

    assert running.started_at is not None
    assert completed.status is JobStatus.SUCCEEDED
    assert completed.completed_at is not None
    assert _count(service_factory, JobOutput) == 1
    with pytest.raises(InvalidStateError):
        service.update_job_status(job.job_id, JobStatus.RUNNING)
    with pytest.raises(ApplicationValidationError):
        service.update_job_status(job.job_id, JobStatus.SUCCEEDED)


def test_tag_comment_and_favorite_soft_delete_restore(service_factory) -> None:
    graph = _seed_graph(service_factory)
    service = CollaborationService(service_factory)
    tag = service.create_tag(
        asset_id=graph.asset.asset_id, name=" hook ", created_by=graph.owner_id
    )
    service.delete_tag(tag.tag_id)
    restored_tag = service.create_tag(
        asset_id=graph.asset.asset_id, name="hook", created_by=graph.owner_id
    )
    favorite = service.add_favorite(
        workspace_id=graph.workspace.workspace_id, asset_id=graph.asset.asset_id
    )
    service.remove_favorite(favorite.favorite_id)
    restored_favorite = service.add_favorite(
        workspace_id=graph.workspace.workspace_id, asset_id=graph.asset.asset_id
    )
    comment = service.create_comment(
        asset_version_id=graph.version.asset_version_id,
        created_by=graph.owner_id,
        body=" 의견 ",
    )
    service.delete_comment(comment.comment_id)

    assert restored_tag.tag_id == tag.tag_id
    assert restored_tag.deleted_at is None
    assert restored_favorite.favorite_id == favorite.favorite_id
    assert restored_favorite.deleted_at is None
    assert service.list_comments(graph.version.asset_version_id) == []
    assert _count(service_factory, Tag) == 1
    assert _count(service_factory, Favorite) == 1
    assert _count(service_factory, Comment) == 1


def test_approval_history_and_recording_enrollment(service_factory) -> None:
    graph = _seed_graph(service_factory, asset_type=AssetType.RECORDING)
    service = CollaborationService(service_factory)
    enrollment = service.create_recording_enrollment(
        workspace_id=graph.workspace.workspace_id,
        recording_asset_version_id=graph.version.asset_version_id,
        status="pending",
        consent_policy_version="1",
        consent_evidence_id="evidence-ref",
        created_by=graph.owner_id,
    )
    first = service.create_approval(
        recording_enrollment_id=enrollment.recording_enrollment_id,
        usage_purpose="voice_conversion",
        status="approved",
        approved_by=graph.owner_id,
        evidence_id="decision-1",
        decided_at=datetime.now(timezone.utc),
    )
    second = service.create_approval(
        recording_enrollment_id=enrollment.recording_enrollment_id,
        usage_purpose="voice_conversion",
        status="revoked",
        approved_by=graph.owner_id,
        evidence_id="decision-2",
        decided_at=datetime.now(timezone.utc),
    )
    history = service.record_history(
        workspace_id=graph.workspace.workspace_id,
        actor_id=graph.owner_id,
        entity_type="recording_enrollment",
        entity_id=enrollment.recording_enrollment_id,
        action="created",
    )

    assert first.approval_id != second.approval_id
    assert (
        len(
            service.list_approvals(
                recording_enrollment_id=enrollment.recording_enrollment_id
            )
        )
        == 2
    )
    assert history.entity_id == enrollment.recording_enrollment_id
    assert _count(service_factory, RecordingEnrollment) == 1
    assert _count(service_factory, Approval) == 2


def test_application_errors_hide_database_details(service_factory) -> None:
    graph = _seed_graph(service_factory)
    with pytest.raises(ResourceConflictError) as captured:
        AssetService(service_factory).create_asset_version(
            asset_id=graph.asset.asset_id,
            version_number=1,
            version_origin="user_created",
            settings_snapshot={},
            created_by=graph.owner_id,
        )

    assert captured.value.code == "RESOURCE_CONFLICT"
    assert "uq_" not in captured.value.message
    assert "asset_versions" not in captured.value.message


def test_service_source_has_no_transport_or_generic_uow_dependencies() -> None:
    service_root = Path(__file__).parents[1] / "services" / "workspace"
    forbidden_names = {"HTTPException", "BaseModel", "UnitOfWork"}
    for path in service_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert names.isdisjoint(forbidden_names)
        assert "backend.schemas" not in path.read_text(encoding="utf-8")
