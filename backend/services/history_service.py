"""History and project use cases."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.core.exceptions import ResourceNotFoundError
from backend.repositories.history_repository import HistoryRepository
from backend.schemas.history import (
    HistoryDetailRead,
    HistoryItemRead,
    ProjectCreate,
    ProjectDetailRead,
    ProjectRead,
    ProjectUpdate,
)


class HistoryService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _item(row: tuple[object, str, bool]) -> HistoryItemRead:
        job, voice_name, has_audio = row
        return HistoryItemRead(
            job_id=job.id,
            project_id=job.project_id,
            title=job.prompt[:200],
            status=job.status,
            created_at=job.created_at,
            duration=job.duration_seconds,
            voice_profile_name=voice_name,
            has_audio=bool(has_audio and job.status == "COMPLETED"),
        )

    def list_history(
        self, limit: int, offset: int, status: str | None, query: str | None
    ) -> list[HistoryItemRead]:
        with self.session_factory() as session:
            rows = HistoryRepository(session).history_rows(
                limit=limit, offset=offset, status=status, query=query
            )
            return [self._item(row) for row in rows]

    def get_history(self, job_id: str) -> HistoryDetailRead:
        with self.session_factory() as session:
            row = HistoryRepository(session).history_detail(job_id)
            if row is None:
                raise ResourceNotFoundError("History 작업")
            item = self._item(row)
            job = row[0]
            return HistoryDetailRead(
                **item.model_dump(),
                prompt=job.prompt,
                genre=job.genre,
                completed_at=job.completed_at,
            )

    def list_projects(self) -> list[ProjectRead]:
        with self.session_factory() as session:
            return [
                ProjectRead.model_validate(project).model_copy(
                    update={"job_count": count}
                )
                for project, count in HistoryRepository(session).list_projects()
            ]

    def get_project(self, project_id: str) -> ProjectDetailRead:
        with self.session_factory() as session:
            repository = HistoryRepository(session)
            project = repository.get_project(project_id)
            if project is None:
                raise ResourceNotFoundError("Project")
            jobs = [
                self._item(row)
                for row in repository.history_rows(
                    limit=100, offset=0, project_id=project_id
                )
            ]
            return ProjectDetailRead(
                id=project.id,
                title=project.title,
                description=project.description,
                created_at=project.created_at,
                updated_at=project.updated_at,
                job_count=len(jobs),
                jobs=jobs,
            )

    def create_project(self, request: ProjectCreate) -> ProjectRead:
        with self.session_factory() as session:
            project = HistoryRepository(session).create_project(
                request.title, request.description
            )
            return ProjectRead.model_validate(project)

    def update_project(self, project_id: str, request: ProjectUpdate) -> ProjectRead:
        with self.session_factory() as session:
            repository = HistoryRepository(session)
            project = repository.get_project(project_id)
            if project is None:
                raise ResourceNotFoundError("Project")
            project = repository.update_project(
                project, request.title, request.description, request.model_fields_set
            )
            return ProjectRead.model_validate(project).model_copy(
                update={"job_count": repository.project_job_count(project.id)}
            )

    def delete_project(self, project_id: str) -> None:
        with self.session_factory() as session:
            repository = HistoryRepository(session)
            project = repository.get_project(project_id)
            if project is None:
                raise ResourceNotFoundError("Project")
            repository.delete_project(project)
