"""Workspace Job lifecycle과 입출력 application use case."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    ApplicationValidationError,
    InvalidStateError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.models.workspace import (
    Job,
    JobInput,
    JobOutput,
    JobStatus,
    ModelUsage,
)
from backend.repositories.workspace import (
    AssetRepository,
    CompositionRepository,
    JobRepository,
    WorkspaceRepository,
)

ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset(
        {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}
TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
)


@dataclass(frozen=True)
class JobReferenceInput:
    input_order: int
    asset_version_id: UUID | None = None
    artifact_id: UUID | None = None


@dataclass(frozen=True)
class JobReferenceOutput:
    output_order: int
    asset_version_id: UUID | None = None
    artifact_id: UUID | None = None


@dataclass(frozen=True)
class ModelUsageInput:
    provider_id: str
    model_manifest_id: str
    model_id: str
    model_version: str
    api_contract_version: str
    license_status: str
    commercial_usage_status: str
    asset_version_id: UUID | None = None
    checkpoint_version: str | None = None


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ApplicationValidationError(f"{field_name}은(는) 비어 있을 수 없습니다.")
    return normalized


class JobService:
    """Job 요청 snapshot과 상태 전이를 transaction 단위로 관리한다."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def create_job(
        self,
        *,
        project_id: UUID,
        job_type: str,
        api_contract_version: str,
        settings_snapshot: dict[str, Any],
        requested_by: UUID,
        inputs: Sequence[JobReferenceInput] = (),
        model_usages: Sequence[ModelUsageInput] = (),
        composition_snapshot_id: UUID | None = None,
        provider_id: str | None = None,
        model_manifest_id: str | None = None,
        retry_of_job_id: UUID | None = None,
    ) -> Job:
        normalized_inputs = self._normalize_inputs(inputs)
        try:
            with self.session_factory() as session, session.begin():
                workspace_repository = WorkspaceRepository(session)
                asset_repository = AssetRepository(session)
                composition_repository = CompositionRepository(session)
                job_repository = JobRepository(session)
                project = workspace_repository.get_project(project_id)
                if project is None:
                    raise ResourceNotFoundError("MusicProject")
                if composition_snapshot_id is not None:
                    snapshot = composition_repository.get_snapshot(
                        composition_snapshot_id
                    )
                    if snapshot is None or snapshot.project_id != project_id:
                        raise ApplicationValidationError(
                            "CompositionSnapshot은 같은 Project에 속해야 합니다."
                        )
                if retry_of_job_id is not None:
                    retry_of = job_repository.get_job(retry_of_job_id)
                    if retry_of is None:
                        raise ResourceNotFoundError("재시도 원본 Job")
                    if retry_of.status not in {
                        JobStatus.FAILED,
                        JobStatus.CANCELLED,
                    }:
                        raise InvalidStateError("재시도 원본 Job")
                for item in normalized_inputs:
                    self._validate_reference(
                        asset_repository,
                        project.workspace_id,
                        asset_version_id=item.asset_version_id,
                        artifact_id=item.artifact_id,
                    )
                job = job_repository.add_job(
                    Job(
                        project_id=project_id,
                        composition_snapshot_id=composition_snapshot_id,
                        job_type=_required_text(job_type, "Job 유형"),
                        status=JobStatus.QUEUED,
                        provider_id=provider_id.strip() if provider_id else None,
                        api_contract_version=_required_text(
                            api_contract_version, "API contract version"
                        ),
                        model_manifest_id=(
                            model_manifest_id.strip() if model_manifest_id else None
                        ),
                        settings_snapshot=dict(settings_snapshot),
                        retry_of_job_id=retry_of_job_id,
                        requested_by=requested_by,
                    )
                )
                for item in normalized_inputs:
                    job_repository.add_job_input(
                        JobInput(
                            job_id=job.job_id,
                            input_order=item.input_order,
                            asset_version_id=item.asset_version_id,
                            artifact_id=item.artifact_id,
                        )
                    )
                for usage_input in model_usages:
                    usage = self._build_model_usage(
                        job.job_id,
                        usage_input,
                        asset_repository,
                        project.workspace_id,
                    )
                    job_repository.add_model_usage(usage)
            return job
        except IntegrityError:
            raise ResourceConflictError("Workspace Job") from None

    def get_job(self, job_id: UUID) -> Job:
        with self.session_factory() as session:
            job = JobRepository(session).get_job(job_id)
            if job is None:
                raise ResourceNotFoundError("Workspace Job")
            return job

    def list_jobs(
        self,
        *,
        project_id: UUID | None = None,
        status: JobStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        with self.session_factory() as session:
            repository = JobRepository(session)
            if project_id is not None:
                if WorkspaceRepository(session).get_project(project_id) is None:
                    raise ResourceNotFoundError("MusicProject")
                return repository.list_project_jobs(
                    project_id, limit=limit, offset=offset
                )
            if status is not None:
                return repository.list_jobs_by_status(
                    status, limit=limit, offset=offset
                )
            return repository.list_jobs(limit=limit, offset=offset)

    def update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        error_retryable: bool | None = None,
        stage: str | None = None,
        progress_percent: Decimal | None = None,
    ) -> Job:
        if status is JobStatus.SUCCEEDED:
            raise ApplicationValidationError(
                "성공 전이는 complete_job_with_outputs를 사용해야 합니다."
            )
        if progress_percent is not None and not Decimal(
            0
        ) <= progress_percent <= Decimal(100):
            raise ApplicationValidationError("진행률은 0에서 100 사이여야 합니다.")
        with self.session_factory() as session, session.begin():
            repository = JobRepository(session)
            job = repository.get_job(job_id)
            if job is None:
                raise ResourceNotFoundError("Workspace Job")
            self._validate_transition(job.status, status)
            now = datetime.now(timezone.utc)
            repository.update_job_status(
                job,
                status,
                started_at=now if status is JobStatus.RUNNING else None,
                completed_at=now if status in TERMINAL_STATUSES else None,
            )
            job.stage = stage.strip() if stage else job.stage
            if progress_percent is not None:
                job.progress_percent = progress_percent
            if status is JobStatus.FAILED:
                job.error_code = _required_text(error_code or "JOB_FAILED", "오류 코드")
                job.error_message = _required_text(
                    error_message or "작업이 실패했습니다.", "오류 메시지"
                )
                job.error_retryable = bool(error_retryable)
            session.flush()
        return job

    def add_job_output(self, job_id: UUID, output: JobReferenceOutput) -> JobOutput:
        normalized = self._normalize_outputs([output])[0]
        try:
            with self.session_factory() as session, session.begin():
                repository = JobRepository(session)
                job = repository.get_job(job_id)
                if job is None:
                    raise ResourceNotFoundError("Workspace Job")
                if job.status is not JobStatus.RUNNING:
                    raise InvalidStateError("Workspace Job")
                project = WorkspaceRepository(session).get_project(job.project_id)
                if project is None:
                    raise ResourceNotFoundError("MusicProject")
                self._validate_reference(
                    AssetRepository(session),
                    project.workspace_id,
                    asset_version_id=normalized.asset_version_id,
                    artifact_id=normalized.artifact_id,
                )
                if repository.job_output_order_exists(job_id, normalized.output_order):
                    raise ResourceConflictError("JobOutput 순서")
                created = repository.add_job_output(
                    JobOutput(
                        job_id=job_id,
                        output_order=normalized.output_order,
                        asset_version_id=normalized.asset_version_id,
                        artifact_id=normalized.artifact_id,
                    )
                )
            return created
        except IntegrityError:
            raise ResourceConflictError("JobOutput") from None

    def complete_job_with_outputs(
        self, job_id: UUID, outputs: Sequence[JobReferenceOutput]
    ) -> Job:
        normalized_outputs = self._normalize_outputs(outputs)
        if not normalized_outputs:
            raise ApplicationValidationError("성공 Job에는 출력이 필요합니다.")
        try:
            with self.session_factory() as session, session.begin():
                job_repository = JobRepository(session)
                job = job_repository.get_job(job_id)
                if job is None:
                    raise ResourceNotFoundError("Workspace Job")
                self._validate_transition(job.status, JobStatus.SUCCEEDED)
                project = WorkspaceRepository(session).get_project(job.project_id)
                if project is None:
                    raise ResourceNotFoundError("MusicProject")
                asset_repository = AssetRepository(session)
                for output in normalized_outputs:
                    self._validate_reference(
                        asset_repository,
                        project.workspace_id,
                        asset_version_id=output.asset_version_id,
                        artifact_id=output.artifact_id,
                    )
                    if job_repository.job_output_order_exists(
                        job_id, output.output_order
                    ):
                        raise ResourceConflictError("JobOutput 순서")
                    job_repository.add_job_output(
                        JobOutput(
                            job_id=job_id,
                            output_order=output.output_order,
                            asset_version_id=output.asset_version_id,
                            artifact_id=output.artifact_id,
                        )
                    )
                job.progress_percent = Decimal(100)
                job_repository.update_job_status(
                    job,
                    JobStatus.SUCCEEDED,
                    completed_at=datetime.now(timezone.utc),
                )
            return job
        except IntegrityError:
            raise ResourceConflictError("Job 완료 결과") from None

    def record_model_usage(
        self, job_id: UUID, usage_input: ModelUsageInput
    ) -> ModelUsage:
        try:
            with self.session_factory() as session, session.begin():
                job_repository = JobRepository(session)
                job = job_repository.get_job(job_id)
                if job is None:
                    raise ResourceNotFoundError("Workspace Job")
                if job.status in TERMINAL_STATUSES:
                    raise InvalidStateError("Workspace Job")
                project = WorkspaceRepository(session).get_project(job.project_id)
                if project is None:
                    raise ResourceNotFoundError("MusicProject")
                usage = self._build_model_usage(
                    job_id,
                    usage_input,
                    AssetRepository(session),
                    project.workspace_id,
                )
                for existing in job_repository.list_model_usages(job_id):
                    if (
                        existing.model_manifest_id == usage.model_manifest_id
                        and existing.asset_version_id == usage.asset_version_id
                    ):
                        raise ResourceConflictError("ModelUsage")
                job_repository.add_model_usage(usage)
            return usage
        except IntegrityError:
            raise ResourceConflictError("ModelUsage") from None

    def list_model_usages(
        self, job_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[ModelUsage]:
        with self.session_factory() as session:
            repository = JobRepository(session)
            if repository.get_job(job_id) is None:
                raise ResourceNotFoundError("Workspace Job")
            return repository.list_model_usages(job_id, limit=limit, offset=offset)

    @staticmethod
    def _validate_transition(current: JobStatus, target: JobStatus) -> None:
        if target not in ALLOWED_TRANSITIONS[current]:
            raise InvalidStateError("Workspace Job")

    @staticmethod
    def _normalize_inputs(
        inputs: Sequence[JobReferenceInput],
    ) -> list[JobReferenceInput]:
        orders: set[int] = set()
        normalized: list[JobReferenceInput] = []
        for item in inputs:
            if item.input_order < 0:
                raise ApplicationValidationError("JobInput 순서는 0 이상이어야 합니다.")
            if item.input_order in orders:
                raise ResourceConflictError("JobInput 순서")
            if (item.asset_version_id is None) == (item.artifact_id is None):
                raise ApplicationValidationError(
                    "JobInput에는 AssetVersion 또는 Artifact 중 하나만 필요합니다."
                )
            orders.add(item.input_order)
            normalized.append(item)
        return normalized

    @staticmethod
    def _normalize_outputs(
        outputs: Sequence[JobReferenceOutput],
    ) -> list[JobReferenceOutput]:
        orders: set[int] = set()
        normalized: list[JobReferenceOutput] = []
        for output in outputs:
            if output.output_order < 0:
                raise ApplicationValidationError(
                    "JobOutput 순서는 0 이상이어야 합니다."
                )
            if output.output_order in orders:
                raise ResourceConflictError("JobOutput 순서")
            if (output.asset_version_id is None) == (output.artifact_id is None):
                raise ApplicationValidationError(
                    "JobOutput에는 AssetVersion 또는 Artifact 중 하나만 필요합니다."
                )
            orders.add(output.output_order)
            normalized.append(output)
        return normalized

    @staticmethod
    def _validate_reference(
        repository: AssetRepository,
        workspace_id: UUID,
        *,
        asset_version_id: UUID | None,
        artifact_id: UUID | None,
    ) -> None:
        if asset_version_id is not None:
            version = repository.get_asset_version(asset_version_id)
            if version is None:
                raise ResourceNotFoundError("AssetVersion")
        else:
            artifact = repository.get_artifact(artifact_id)
            if artifact is None:
                raise ResourceNotFoundError("Artifact")
            version = repository.get_asset_version(artifact.asset_version_id)
            if version is None:
                raise ResourceNotFoundError("AssetVersion")
        asset = repository.get_asset(version.asset_id)
        if asset is None:
            raise ResourceNotFoundError("Asset")
        if asset.workspace_id is not None and asset.workspace_id != workspace_id:
            raise ApplicationValidationError(
                "Job 입출력의 Workspace 범위가 일치하지 않습니다."
            )

    @staticmethod
    def _build_model_usage(
        job_id: UUID,
        value: ModelUsageInput,
        asset_repository: AssetRepository,
        workspace_id: UUID,
    ) -> ModelUsage:
        if value.asset_version_id is not None:
            JobService._validate_reference(
                asset_repository,
                workspace_id,
                asset_version_id=value.asset_version_id,
                artifact_id=None,
            )
        return ModelUsage(
            job_id=job_id,
            asset_version_id=value.asset_version_id,
            provider_id=_required_text(value.provider_id, "Provider ID"),
            model_manifest_id=_required_text(
                value.model_manifest_id, "Model Manifest ID"
            ),
            model_id=_required_text(value.model_id, "Model ID"),
            model_version=_required_text(value.model_version, "Model version"),
            checkpoint_version=(
                value.checkpoint_version.strip() if value.checkpoint_version else None
            ),
            api_contract_version=_required_text(
                value.api_contract_version, "API contract version"
            ),
            license_status=_required_text(value.license_status, "License 상태"),
            commercial_usage_status=_required_text(
                value.commercial_usage_status, "상업 이용 상태"
            ),
        )
