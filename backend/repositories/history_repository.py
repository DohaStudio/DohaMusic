"""Persistence for generation history and projects."""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.models.project import Project
from backend.models.voice_profile import VoiceProfile


class HistoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_default_project(self) -> Project:
        project = self.session.scalar(select(Project).where(Project.is_default.is_(True)))
        if project is None:
            project = Project(title="Default Project", is_default=True)
            self.session.add(project)
            self.session.flush()
        return project

    def get_project(self, project_id: str) -> Project | None:
        return self.session.get(Project, project_id)

    def create_project(self, title: str, description: str | None) -> Project:
        project = Project(title=title.strip(), description=description)
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def list_projects(self) -> list[tuple[Project, int]]:
        statement = (
            select(Project, func.count(PipelineJob.id))
            .outerjoin(PipelineJob, PipelineJob.project_id == Project.id)
            .group_by(Project.id)
            .order_by(Project.updated_at.desc(), Project.created_at.desc())
        )
        return list(self.session.execute(statement).all())

    def project_job_count(self, project_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count(PipelineJob.id)).where(PipelineJob.project_id == project_id)
            )
            or 0
        )

    def update_project(
        self,
        project: Project,
        title: str | None,
        description: str | None,
        fields: set[str],
    ) -> Project:
        if "title" in fields and title is not None:
            project.title = title.strip()
        if "description" in fields:
            project.description = description
        project.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(project)
        return project

    def delete_project(self, project: Project) -> None:
        self.session.execute(
            update(PipelineJob).where(PipelineJob.project_id == project.id).values(project_id=None)
        )
        self.session.delete(project)
        self.session.commit()

    def history_rows(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        query: str | None = None,
        project_id: str | None = None,
    ) -> list[tuple[PipelineJob, str, bool]]:
        audio_exists = (
            select(PipelineFile.id)
            .where(
                PipelineFile.job_id == PipelineJob.id,
                PipelineFile.file_type == "final",
            )
            .exists()
        )
        statement = select(PipelineJob, VoiceProfile.name, audio_exists).join(
            VoiceProfile, VoiceProfile.id == PipelineJob.voice_profile_id
        )
        if status:
            statement = statement.where(PipelineJob.status == status)
        if query:
            statement = statement.where(PipelineJob.prompt.ilike(f"%{query.strip()}%"))
        if project_id:
            statement = statement.where(PipelineJob.project_id == project_id)
        statement = statement.order_by(PipelineJob.created_at.desc()).offset(offset).limit(limit)
        return list(self.session.execute(statement).all())

    def history_detail(self, job_id: str) -> tuple[PipelineJob, str, bool] | None:
        audio_exists = (
            select(PipelineFile.id)
            .where(
                PipelineFile.job_id == PipelineJob.id,
                PipelineFile.file_type == "final",
            )
            .exists()
        )
        return self.session.execute(
            select(PipelineJob, VoiceProfile.name, audio_exists)
            .join(VoiceProfile, VoiceProfile.id == PipelineJob.voice_profile_id)
            .where(PipelineJob.id == job_id)
        ).one_or_none()
