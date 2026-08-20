"""Provider Job durable binding repository/service contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import backend.models  # noqa: F401
from backend.core.exceptions import (
    ApplicationValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.db.base import Base
from backend.db.sqlite import configure_sqlite_foreign_keys
from backend.models.workspace import (
    Job,
    JobStatus,
    MusicProject,
    ProviderJobBinding,
    Workspace,
)
from backend.repositories.workspace import ProviderJobRepository
from backend.services.workspace import (
    ProviderJobPersistenceError,
    ProviderJobPersistenceErrorReason,
    ProviderJobPersistenceService,
    ProviderJobPersistenceStorageError,
)


@pytest.fixture
def persistence(tmp_path):
    engine = configure_sqlite_foreign_keys(
        create_engine(f"sqlite:///{(tmp_path / 'provider-jobs.db').as_posix()}")
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def _seed_job(
    factory,
    *,
    owner_id: UUID | None = None,
    provider_id: str = "dohavocal",
) -> tuple[UUID, UUID]:
    owner_id = owner_id or uuid4()
    with factory.begin() as session:
        workspace = Workspace(
            owner_id=owner_id,
            name="Provider persistence",
            lifecycle_status="active",
        )
        session.add(workspace)
        session.flush()
        project = MusicProject(
            workspace_id=workspace.workspace_id,
            title="Vocal project",
            description=None,
            lifecycle_status="active",
            created_by=owner_id,
        )
        session.add(project)
        session.flush()
        job = Job(
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            composition_snapshot_id=None,
            job_type="vocal_generation",
            status=JobStatus.QUEUED,
            provider_id=provider_id,
            api_contract_version="0.1.0",
            model_manifest_id="manifest-1",
            progress_percent=None,
            stage=None,
            settings_snapshot={},
            retry_of_job_id=None,
            requested_by=owner_id,
            attempt=0,
        )
        session.add(job)
        session.flush()
        return owner_id, job.job_id


def test_binding_survives_new_service_and_supports_retry_history(persistence) -> None:
    owner_id, job_id = _seed_job(persistence)
    first_service = ProviderJobPersistenceService(persistence)
    first = first_service.create_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=job_id,
        provider_id="dohavocal",
        provider_job_id="provider-job-1",
    )
    second = first_service.create_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=job_id,
        provider_id="dohavocal",
        provider_job_id="provider-job-2",
        retry_of_provider_job_id="provider-job-1",
    )

    restarted_service = ProviderJobPersistenceService(persistence)
    history = restarted_service.list_bindings_for_owner(
        effective_owner_id=owner_id, workspace_job_id=job_id
    )
    latest = restarted_service.get_latest_binding_for_owner(
        effective_owner_id=owner_id, workspace_job_id=job_id
    )

    assert [item.provider_job_id for item in history] == [
        "provider-job-1",
        "provider-job-2",
    ]
    assert history[0].provider_job_binding_id == first.provider_job_binding_id
    assert history[1].retry_of_provider_job_id == "provider-job-1"
    assert latest is not None
    assert latest.provider_job_binding_id == second.provider_job_binding_id


def test_missing_binding_is_normal_recovery_state(persistence) -> None:
    owner_id, job_id = _seed_job(persistence)
    service = ProviderJobPersistenceService(persistence)

    assert (
        service.list_bindings_for_owner(
            effective_owner_id=owner_id, workspace_job_id=job_id
        )
        == ()
    )
    assert (
        service.get_latest_binding_for_owner(
            effective_owner_id=owner_id, workspace_job_id=job_id
        )
        is None
    )


def test_duplicate_provider_identity_is_fail_closed(persistence) -> None:
    owner_id, job_id = _seed_job(persistence)
    service = ProviderJobPersistenceService(persistence)
    service.create_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=job_id,
        provider_id="dohavocal",
        provider_job_id="duplicate-1",
    )

    with pytest.raises(ResourceConflictError):
        service.create_binding_for_owner(
            effective_owner_id=owner_id,
            workspace_job_id=job_id,
            provider_id="dohavocal",
            provider_job_id="duplicate-1",
        )

    assert (
        len(
            service.list_bindings_for_owner(
                effective_owner_id=owner_id, workspace_job_id=job_id
            )
        )
        == 1
    )


def test_unrelated_integrity_error_is_not_mapped_as_duplicate(
    persistence, monkeypatch
) -> None:
    owner_id, job_id = _seed_job(persistence)

    def fail_with_unrelated_integrity_error(*_args, **_kwargs):
        raise IntegrityError("insert", {}, Exception("foreign key failure"))

    monkeypatch.setattr(
        ProviderJobRepository,
        "add_binding",
        fail_with_unrelated_integrity_error,
    )

    with pytest.raises(ProviderJobPersistenceStorageError) as error:
        ProviderJobPersistenceService(persistence).create_binding_for_owner(
            effective_owner_id=owner_id,
            workspace_job_id=job_id,
            provider_id="dohavocal",
            provider_job_id="storage-failure",
        )

    assert error.value.code == "PROVIDER_JOB_PERSISTENCE_FAILED"
    assert "foreign key failure" not in error.value.message


@pytest.mark.parametrize(
    ("provider_id", "provider_job_id", "reason"),
    [
        (
            "DohaVocal",
            "valid-id",
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_ID,
        ),
        (
            "dohavocal",
            "https://provider/jobs/1",
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_JOB_ID,
        ),
        (
            "dohavocal",
            "C:\\jobs\\1",
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_JOB_ID,
        ),
        (
            "dohavocal",
            '{"job":"1"}',
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_JOB_ID,
        ),
        (
            "dohavocal",
            "https:provider-job-1",
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_JOB_ID,
        ),
        (
            "dohavocal",
            "Bearer:credential-value",
            ProviderJobPersistenceErrorReason.INVALID_PROVIDER_JOB_ID,
        ),
    ],
)
def test_identity_validation_rejects_non_logical_values(
    persistence, provider_id, provider_job_id, reason
) -> None:
    owner_id, job_id = _seed_job(persistence)

    with pytest.raises(ProviderJobPersistenceError) as error:
        ProviderJobPersistenceService(persistence).create_binding_for_owner(
            effective_owner_id=owner_id,
            workspace_job_id=job_id,
            provider_id=provider_id,
            provider_job_id=provider_job_id,
        )

    assert error.value.reason == reason


@pytest.mark.parametrize(
    "provider_job_id",
    ["tokenized-job-1", "passwordless-job-1", "secretariat-job-1"],
)
def test_identity_validation_allows_non_sensitive_word_substrings(
    persistence, provider_job_id
) -> None:
    owner_id, job_id = _seed_job(persistence)

    binding = ProviderJobPersistenceService(persistence).create_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=job_id,
        provider_id="dohavocal",
        provider_job_id=provider_job_id,
    )

    assert binding.provider_job_id == provider_job_id


def test_owner_scope_and_job_provider_are_fail_closed(persistence) -> None:
    owner_id, job_id = _seed_job(persistence)
    service = ProviderJobPersistenceService(persistence)

    with pytest.raises(ResourceNotFoundError):
        service.create_binding_for_owner(
            effective_owner_id=uuid4(),
            workspace_job_id=job_id,
            provider_id="dohavocal",
            provider_job_id="hidden-job",
        )
    with pytest.raises(ProviderJobPersistenceError) as mismatch:
        service.create_binding_for_owner(
            effective_owner_id=owner_id,
            workspace_job_id=job_id,
            provider_id="dohaaudio",
            provider_job_id="wrong-provider",
        )
    assert (
        mismatch.value.reason == ProviderJobPersistenceErrorReason.JOB_PROVIDER_MISMATCH
    )

    _, second_job_id = _seed_job(persistence, owner_id=owner_id)
    with persistence.begin() as session:
        job = session.get(Job, job_id)
        second_job = session.get(Job, second_job_id)
        assert job is not None and second_job is not None
        job.workspace_id = second_job.workspace_id
    with pytest.raises(ResourceNotFoundError):
        service.get_latest_binding_for_owner(
            effective_owner_id=owner_id, workspace_job_id=job_id
        )


def test_retry_lineage_rejects_invalid_parent_relations_atomically(persistence) -> None:
    owner_id, first_job_id = _seed_job(persistence)
    _, second_job_id = _seed_job(persistence, owner_id=owner_id)
    other_owner, other_provider_job_id = _seed_job(persistence, provider_id="dohaaudio")
    service = ProviderJobPersistenceService(persistence)
    service.create_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=first_job_id,
        provider_id="dohavocal",
        provider_job_id="first-parent",
    )
    service.create_binding_for_owner(
        effective_owner_id=other_owner,
        workspace_job_id=other_provider_job_id,
        provider_id="dohaaudio",
        provider_job_id="audio-parent",
    )

    cases = (
        (
            second_job_id,
            "child-cross-job",
            "first-parent",
            ProviderJobPersistenceErrorReason.RETRY_CROSS_WORKSPACE,
        ),
        (
            first_job_id,
            "child-cross-provider",
            "audio-parent",
            ProviderJobPersistenceErrorReason.RETRY_CROSS_PROVIDER,
        ),
        (
            first_job_id,
            "child-missing",
            "missing-parent",
            ProviderJobPersistenceErrorReason.RETRY_PARENT_NOT_FOUND,
        ),
        (
            first_job_id,
            "self-child",
            "self-child",
            ProviderJobPersistenceErrorReason.RETRY_SELF_REFERENCE,
        ),
    )
    for job_id, child_id, parent_id, reason in cases:
        with pytest.raises(ProviderJobPersistenceError) as error:
            service.create_binding_for_owner(
                effective_owner_id=owner_id,
                workspace_job_id=job_id,
                provider_id="dohavocal",
                provider_job_id=child_id,
                retry_of_provider_job_id=parent_id,
            )
        assert error.value.reason == reason

    assert [
        item.provider_job_id
        for item in service.list_bindings_for_owner(
            effective_owner_id=owner_id, workspace_job_id=first_job_id
        )
    ] == ["first-parent"]


def test_repository_identity_lookup_and_database_constraints(persistence) -> None:
    owner_id, job_id = _seed_job(persistence)
    binding = ProviderJobPersistenceService(persistence).create_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=job_id,
        provider_id="dohavocal",
        provider_job_id="repository-lookup",
    )

    with persistence() as session:
        repository = ProviderJobRepository(session)
        assert repository.get_by_id(binding.provider_job_binding_id) is not None
        assert (
            repository.get_by_provider_identity("dohavocal", "repository-lookup")
            is not None
        )

    with pytest.raises(IntegrityError), persistence.begin() as session:
        session.add(
            ProviderJobBinding(
                workspace_job_id=uuid4(),
                provider_id="dohavocal",
                provider_job_id="missing-workspace-job",
            )
        )
        session.flush()

    with pytest.raises(IntegrityError), persistence.begin() as session:
        session.execute(delete(Job).where(Job.job_id == job_id))


def test_provider_identity_namespace_and_latest_order_are_deterministic(
    persistence,
) -> None:
    owner_id, vocal_job_id = _seed_job(persistence)
    audio_owner_id, audio_job_id = _seed_job(persistence, provider_id="dohaaudio")
    service = ProviderJobPersistenceService(persistence)
    shared_provider_job_id = "shared-provider-job-id"
    vocal = service.create_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=vocal_job_id,
        provider_id="dohavocal",
        provider_job_id=shared_provider_job_id,
    )
    audio = service.create_binding_for_owner(
        effective_owner_id=audio_owner_id,
        workspace_job_id=audio_job_id,
        provider_id="dohaaudio",
        provider_job_id=shared_provider_job_id,
    )
    assert vocal.provider_job_id == audio.provider_job_id
    assert vocal.provider_id != audio.provider_id

    shared_created_at = datetime(2099, 8, 21, tzinfo=UTC)
    lower_id = UUID(int=1)
    higher_id = UUID(int=2)
    with persistence.begin() as session:
        session.add_all(
            [
                ProviderJobBinding(
                    provider_job_binding_id=lower_id,
                    workspace_job_id=vocal_job_id,
                    provider_id="dohavocal",
                    provider_job_id="same-time-lower",
                    created_at=shared_created_at,
                ),
                ProviderJobBinding(
                    provider_job_binding_id=higher_id,
                    workspace_job_id=vocal_job_id,
                    provider_id="dohavocal",
                    provider_job_id="same-time-higher",
                    created_at=shared_created_at,
                ),
            ]
        )

    latest = service.get_latest_binding_for_owner(
        effective_owner_id=owner_id,
        workspace_job_id=vocal_job_id,
    )
    assert latest is not None
    assert latest.provider_job_binding_id == higher_id


def test_list_limit_validation(persistence) -> None:
    owner_id, job_id = _seed_job(persistence)
    with pytest.raises(ApplicationValidationError):
        ProviderJobPersistenceService(persistence).list_bindings_for_owner(
            effective_owner_id=owner_id,
            workspace_job_id=job_id,
            limit=0,
        )
