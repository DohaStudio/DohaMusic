"""Workspace Repository의 additive transaction·query 계약 검증."""

from __future__ import annotations

from datetime import UTC, datetime
from inspect import getsource
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.pipeline_job import PipelineJob
from backend.models.workspace import (
    WORKSPACE_ENTITY_CLASSES,
    Approval,
    Artifact,
    Asset,
    AssetRelation,
    AssetType,
    AssetVersion,
    Comment,
    CompositionSnapshot,
    Favorite,
    History,
    Job,
    JobInput,
    JobOutput,
    JobStatus,
    ModelUsage,
    MusicProject,
    ProcessingChain,
    ProcessingStep,
    ProjectAsset,
    RecordingEnrollment,
    SnapshotItem,
    Tag,
    Workspace,
)
from backend.repositories.workspace import (
    AssetRepository,
    CollaborationRepository,
    CompositionRepository,
    JobRepository,
    WorkspaceRepository,
)


class TrackingSession(Session):
    """Repository의 transaction 종료 호출을 감시하는 테스트 Session."""

    commit_calls = 0
    rollback_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1
        super().commit()

    def rollback(self) -> None:
        self.rollback_calls += 1
        super().rollback()


@pytest.fixture
def session_factory(tmp_path):
    database_path = tmp_path / "workspace-repositories.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    workspace_tables = [entity.__table__ for entity in WORKSPACE_ENTITY_CLASSES]
    Base.metadata.create_all(engine, tables=workspace_tables)
    factory = sessionmaker(
        bind=engine,
        class_=TrackingSession,
        autoflush=False,
        expire_on_commit=False,
    )
    yield factory
    engine.dispose()


@pytest.fixture
def session(session_factory):
    with session_factory() as value:
        yield value


def _workspace(owner_id: UUID | None = None, *, name: str = "개인 작업공간") -> Workspace:
    return Workspace(
        owner_id=owner_id or uuid4(),
        name=name,
        lifecycle_status="active",
    )


def _project(workspace: Workspace, *, title: str = "테스트 곡") -> MusicProject:
    return MusicProject(
        workspace_id=workspace.workspace_id,
        title=title,
        description=None,
        lifecycle_status="active",
        created_by=workspace.owner_id,
    )


def _asset(workspace: Workspace, asset_type: AssetType = AssetType.MUSIC) -> Asset:
    return Asset(
        workspace_id=workspace.workspace_id,
        owner_id=workspace.owner_id,
        asset_type=asset_type,
        lifecycle_status="active",
    )


def _version(asset: Asset, number: int = 1) -> AssetVersion:
    return AssetVersion(
        asset_id=asset.asset_id,
        version_number=number,
        version_origin="provider",
        settings_snapshot={},
        created_by=asset.owner_id,
    )


def _seed_asset(
    session: TrackingSession,
) -> tuple[Workspace, MusicProject, Asset, AssetVersion]:
    workspace_repository = WorkspaceRepository(session)
    asset_repository = AssetRepository(session)
    workspace = workspace_repository.add_workspace(_workspace())
    project = workspace_repository.add_project(_project(workspace))
    asset = asset_repository.add_asset(_asset(workspace))
    version = asset_repository.add_asset_version(_version(asset))
    return workspace, project, asset, version


def test_repository_session_injection_and_external_rollback(
    session_factory, session: TrackingSession
) -> None:
    repository = WorkspaceRepository(session)
    workspace = repository.add_workspace(_workspace())

    assert repository.session is session
    assert workspace.workspace_id is not None
    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    with session_factory() as other:
        assert other.get(Workspace, workspace.workspace_id) is None

    session.rollback()
    with session_factory() as other:
        assert other.get(Workspace, workspace.workspace_id) is None


def test_workspace_repository_queries_soft_delete_and_project_asset_constraints(
    session: TrackingSession,
) -> None:
    repository = WorkspaceRepository(session)
    asset_repository = AssetRepository(session)
    workspace = repository.add_workspace(_workspace())
    project = repository.add_project(_project(workspace))
    first_asset = asset_repository.add_asset(_asset(workspace))
    second_asset = asset_repository.add_asset(_asset(workspace, AssetType.VOCAL))
    second_link = repository.add_project_asset(
        ProjectAsset(
            project_id=project.project_id,
            asset_id=second_asset.asset_id,
            role="vocal",
            display_order=2,
        )
    )
    first_link = repository.add_project_asset(
        ProjectAsset(
            project_id=project.project_id,
            asset_id=first_asset.asset_id,
            role="music",
            display_order=1,
        )
    )

    assert (
        repository.get_workspace_for_owner(workspace.workspace_id, workspace.owner_id) == workspace
    )
    assert repository.workspace_name_exists(workspace.owner_id, workspace.name)
    assert repository.project_title_exists(workspace.workspace_id, project.title)
    assert repository.project_asset_exists(project.project_id, first_asset.asset_id)
    assert repository.list_project_assets(project.project_id) == [
        first_link,
        second_link,
    ]

    repository.set_project_asset_display_order(second_link, 0)
    assert repository.list_project_assets(project.project_id)[0] == second_link
    repository.remove_project_asset(first_link)
    assert repository.get_project_asset(first_link.project_asset_id) is None
    assert (
        repository.get_project_asset(first_link.project_asset_id, include_deleted=True)
        == first_link
    )

    duplicate = ProjectAsset(
        project_id=project.project_id,
        asset_id=second_asset.asset_id,
        role="duplicate",
        display_order=3,
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()


def test_asset_repository_versions_artifacts_relations_and_immutability(
    session: TrackingSession,
) -> None:
    workspace, _, source_asset, first_version = _seed_asset(session)
    repository = AssetRepository(session)
    second_version = repository.add_asset_version(_version(source_asset, 2))
    target_asset = repository.add_asset(_asset(workspace, AssetType.VOCAL))
    artifact = repository.add_artifact(
        Artifact(
            asset_version_id=first_version.asset_version_id,
            artifact_kind="provider_output",
            media_type="audio/wav",
            size_bytes=128,
            checksum_algorithm="sha256",
            artifact_checksum="abc123",
            producer_type="provider",
            retention_status="active",
        )
    )
    clip_source = repository.add_artifact(
        Artifact(
            asset_version_id=first_version.asset_version_id,
            artifact_kind="audio",
            media_type="audio/wav",
            size_bytes=128,
            duration_us=2_000,
            checksum_algorithm="sha256",
            artifact_checksum="duration-source",
            producer_type="workspace",
            retention_status="active",
        )
    )
    inactive_source = repository.add_artifact(
        Artifact(
            asset_version_id=first_version.asset_version_id,
            artifact_kind="audio",
            media_type="audio/wav",
            size_bytes=128,
            duration_us=2_000,
            checksum_algorithm="sha256",
            artifact_checksum="inactive-source",
            producer_type="workspace",
            retention_status="expired",
        )
    )
    relation = repository.add_asset_relation(
        AssetRelation(
            source_asset_id=source_asset.asset_id,
            target_asset_id=target_asset.asset_id,
            relation_type="derived_vocal",
        )
    )

    assert "project_id" not in Asset.__table__.columns
    assert not any("path" in column.name for column in Artifact.__table__.columns)
    assert not hasattr(repository, "update_asset_version")
    assert repository.list_asset_versions(source_asset.asset_id) == [
        first_version,
        second_version,
    ]
    assert repository.get_latest_asset_version(source_asset.asset_id) == second_version
    assert repository.version_number_exists(source_asset.asset_id, 2)
    version_artifacts = repository.list_version_artifacts(first_version.asset_version_id)
    assert {item.artifact_id for item in version_artifacts} == {
        artifact.artifact_id,
        clip_source.artifact_id,
        inactive_source.artifact_id,
    }
    assert repository.list_clip_source_artifact_candidates(first_version.asset_version_id) == [
        clip_source
    ]
    assert repository.checksum_exists("sha256", "abc123")
    assert repository.list_asset_relations(asset_id=source_asset.asset_id) == [relation]
    assert repository.relation_exists(
        relation_type="derived_vocal",
        source_asset_id=source_asset.asset_id,
        target_asset_id=target_asset.asset_id,
    )

    session.add(_version(source_asset, 2))
    with pytest.raises(IntegrityError):
        session.flush()


def test_composition_repository_keeps_exact_versions_and_stable_order(
    session: TrackingSession,
) -> None:
    workspace, project, asset, version = _seed_asset(session)
    repository = CompositionRepository(session)
    chain = repository.add_processing_chain(
        ProcessingChain(
            name="mix",
            chain_version="1",
            chain_checksum="chain-1",
            created_by=workspace.owner_id,
        )
    )
    second_step = repository.add_processing_step(
        ProcessingStep(
            processing_chain_id=chain.processing_chain_id,
            step_order=2,
            step_type="limiter",
            settings_snapshot={},
        )
    )
    first_step = repository.add_processing_step(
        ProcessingStep(
            processing_chain_id=chain.processing_chain_id,
            step_order=1,
            step_type="gain",
            settings_snapshot={},
        )
    )
    snapshot = repository.add_snapshot(
        CompositionSnapshot(
            project_id=project.project_id,
            snapshot_version=1,
            processing_chain_id=chain.processing_chain_id,
            mix_settings_snapshot={},
            provider_versions={},
            model_manifest_ids={},
            created_by=workspace.owner_id,
        )
    )
    item = repository.add_snapshot_item(
        SnapshotItem(
            composition_snapshot_id=snapshot.composition_snapshot_id,
            asset_version_id=version.asset_version_id,
            item_role="music",
            sort_order=1,
        )
    )

    assert not hasattr(repository, "update_snapshot")
    assert repository.list_snapshot_items(snapshot.composition_snapshot_id) == [item]
    assert repository.snapshot_item_exists(
        snapshot.composition_snapshot_id, version.asset_version_id, "music"
    )
    assert repository.list_asset_snapshots(asset.asset_id) == [snapshot]
    assert repository.list_processing_steps(chain.processing_chain_id) == [
        first_step,
        second_step,
    ]
    assert repository.processing_step_order_exists(chain.processing_chain_id, 1)


def test_job_repository_is_separate_from_pipeline_and_orders_inputs_outputs(
    session: TrackingSession,
) -> None:
    workspace, project, _, version = _seed_asset(session)
    asset_repository = AssetRepository(session)
    artifact = asset_repository.add_artifact(
        Artifact(
            asset_version_id=version.asset_version_id,
            artifact_kind="source",
            media_type="audio/wav",
            size_bytes=64,
            checksum_algorithm="sha256",
            artifact_checksum="job-source",
            producer_type="workspace",
            retention_status="active",
        )
    )
    repository = JobRepository(session)
    job = repository.add_job(
        Job(
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            job_type="mix",
            status=JobStatus.QUEUED,
            api_contract_version="0.1.0",
            settings_snapshot={},
            requested_by=workspace.owner_id,
        )
    )
    second_input = repository.add_job_input(
        JobInput(job_id=job.job_id, artifact_id=artifact.artifact_id, input_order=2)
    )
    first_input = repository.add_job_input(
        JobInput(
            job_id=job.job_id,
            asset_version_id=version.asset_version_id,
            input_order=1,
        )
    )
    output = repository.add_job_output(
        JobOutput(
            job_id=job.job_id,
            asset_version_id=version.asset_version_id,
            output_order=1,
        )
    )
    usage = repository.add_model_usage(
        ModelUsage(
            job_id=job.job_id,
            asset_version_id=version.asset_version_id,
            provider_id="dohatest",
            model_manifest_id="manifest-1",
            model_id="model-1",
            model_version="1",
            api_contract_version="0.1.0",
            license_status="reviewed",
            commercial_usage_status="allowed",
        )
    )

    assert Job.__table__.name == "jobs"
    assert PipelineJob.__table__.name == "pipeline_jobs"
    assert repository.list_jobs_by_status(JobStatus.QUEUED) == [job]
    assert repository.list_job_inputs(job.job_id) == [first_input, second_input]
    assert repository.list_job_outputs(job.job_id) == [output]
    assert repository.list_model_usages(job.job_id) == [usage]
    assert repository.job_input_order_exists(job.job_id, 1)
    assert repository.job_output_order_exists(job.job_id, 1)
    repository.update_job_status(job, JobStatus.SUCCEEDED, completed_at=datetime.now(UTC))
    assert job.status == JobStatus.SUCCEEDED
    assert session.commit_calls == 0


def test_collaboration_repository_metadata_constraints_and_soft_delete(
    session: TrackingSession,
) -> None:
    workspace, _, asset, version = _seed_asset(session)
    repository = CollaborationRepository(session)
    enrollment = repository.add_recording_enrollment(
        RecordingEnrollment(
            workspace_id=workspace.workspace_id,
            recording_asset_version_id=version.asset_version_id,
            status="approved",
            consent_policy_version="1",
            consent_evidence_id="evidence-1",
            created_by=workspace.owner_id,
        )
    )
    tag = repository.add_tag(
        Tag(asset_id=asset.asset_id, name="favorite", created_by=workspace.owner_id)
    )
    comment = repository.add_comment(
        Comment(
            asset_version_id=version.asset_version_id,
            created_by=workspace.owner_id,
            body="검토 의견",
        )
    )
    favorite = repository.add_favorite(
        Favorite(workspace_id=workspace.workspace_id, asset_id=asset.asset_id)
    )
    history = repository.add_history(
        History(
            workspace_id=workspace.workspace_id,
            actor_id=workspace.owner_id,
            entity_type="asset",
            entity_id=asset.asset_id,
            action="created",
        )
    )
    approval = repository.add_approval(
        Approval(
            recording_enrollment_id=enrollment.recording_enrollment_id,
            usage_purpose="training",
            status="approved",
            approved_by=workspace.owner_id,
            evidence_id="approval-1",
            decided_at=datetime.now(UTC),
        )
    )

    assert repository.get_recording_enrollment(enrollment.recording_enrollment_id) == enrollment
    assert repository.tag_name_exists(asset.asset_id, tag.name)
    assert repository.favorite_exists(workspace.workspace_id, asset.asset_id)
    assert repository.list_history(workspace.workspace_id) == [history]
    assert repository.approval_exists(
        usage_purpose="training",
        recording_enrollment_id=enrollment.recording_enrollment_id,
    )
    assert repository.list_approvals(
        recording_enrollment_id=enrollment.recording_enrollment_id
    ) == [approval]

    repository.soft_delete_comment(comment)
    repository.remove_favorite(favorite)
    assert repository.get_comment(comment.comment_id) is None
    assert repository.get_comment(comment.comment_id, include_deleted=True) == comment
    assert repository.get_favorite(favorite.favorite_id) is None

    session.add(Tag(asset_id=asset.asset_id, name=tag.name, created_by=workspace.owner_id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_workspace_tables_only_and_foreign_keys_are_active(
    session: TrackingSession,
) -> None:
    table_names = set(inspect(session.bind).get_table_names())

    assert table_names == {entity.__tablename__ for entity in WORKSPACE_ENTITY_CLASSES}
    assert session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    session.add(
        MusicProject(
            workspace_id=uuid4(),
            title="고아 프로젝트",
            lifecycle_status="active",
            created_by=uuid4(),
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_repository_classes_never_end_transactions() -> None:
    repository_classes = (
        WorkspaceRepository,
        AssetRepository,
        CompositionRepository,
        JobRepository,
        CollaborationRepository,
    )

    for repository_class in repository_classes:
        names = {
            name for name in dir(repository_class) if callable(getattr(repository_class, name))
        }
        assert "commit" not in names
        assert "rollback" not in names
        source = getsource(repository_class)
        assert ".commit(" not in source
        assert ".rollback(" not in source
