"""Workspace와 MusicProject application use case."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    ApplicationValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.models.workspace import Asset, MusicProject, ProjectAsset, Workspace
from backend.repositories.workspace import AssetRepository, WorkspaceRepository


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ApplicationValidationError(f"{field_name}은(는) 비어 있을 수 없습니다.")
    return normalized


class WorkspaceService:
    """Workspace aggregate의 transaction 경계를 소유한다."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def create_workspace(
        self,
        *,
        owner_id: UUID,
        name: str,
        lifecycle_status: str = "active",
    ) -> Workspace:
        normalized_name = _required_text(name, "Workspace 이름")
        normalized_status = _required_text(lifecycle_status, "Workspace 상태")
        try:
            with self.session_factory() as session, session.begin():
                repository = WorkspaceRepository(session)
                if repository.workspace_name_exists(owner_id, normalized_name):
                    raise ResourceConflictError("Workspace 이름")
                workspace = repository.add_workspace(
                    Workspace(
                        owner_id=owner_id,
                        name=normalized_name,
                        lifecycle_status=normalized_status,
                    )
                )
            return workspace
        except IntegrityError:
            raise ResourceConflictError("Workspace") from None

    def get_workspace(self, workspace_id: UUID) -> Workspace:
        with self.session_factory() as session:
            workspace = WorkspaceRepository(session).get_workspace(workspace_id)
            if workspace is None:
                raise ResourceNotFoundError("Workspace")
            return workspace

    def list_workspaces(
        self,
        *,
        owner_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Workspace]:
        with self.session_factory() as session:
            return WorkspaceRepository(session).list_workspaces(
                owner_id=owner_id, limit=limit, offset=offset
            )

    def rename_workspace(self, workspace_id: UUID, name: str) -> Workspace:
        normalized_name = _required_text(name, "Workspace 이름")
        with self.session_factory() as session, session.begin():
            repository = WorkspaceRepository(session)
            workspace = repository.get_workspace(workspace_id)
            if workspace is None:
                raise ResourceNotFoundError("Workspace")
            if repository.workspace_name_exists(workspace.owner_id, normalized_name):
                if workspace.name != normalized_name:
                    raise ResourceConflictError("Workspace 이름")
            workspace.name = normalized_name
            session.flush()
        return workspace

    def delete_workspace(self, workspace_id: UUID) -> Workspace:
        with self.session_factory() as session, session.begin():
            repository = WorkspaceRepository(session)
            workspace = repository.get_workspace(workspace_id)
            if workspace is None:
                raise ResourceNotFoundError("Workspace")
            repository.soft_delete_workspace(workspace)
        return workspace

    def create_project(
        self,
        *,
        workspace_id: UUID,
        title: str,
        created_by: UUID,
        description: str | None = None,
        lifecycle_status: str = "active",
    ) -> MusicProject:
        normalized_title = _required_text(title, "Project 제목")
        normalized_status = _required_text(lifecycle_status, "Project 상태")
        normalized_description = (
            description.strip() if description is not None else None
        )
        try:
            with self.session_factory() as session, session.begin():
                repository = WorkspaceRepository(session)
                if repository.get_workspace(workspace_id) is None:
                    raise ResourceNotFoundError("Workspace")
                if repository.project_title_exists(workspace_id, normalized_title):
                    raise ResourceConflictError("Project 제목")
                project = repository.add_project(
                    MusicProject(
                        workspace_id=workspace_id,
                        title=normalized_title,
                        description=normalized_description,
                        lifecycle_status=normalized_status,
                        created_by=created_by,
                    )
                )
            return project
        except IntegrityError:
            raise ResourceConflictError("MusicProject") from None

    def get_project(self, project_id: UUID) -> MusicProject:
        with self.session_factory() as session:
            project = WorkspaceRepository(session).get_project(project_id)
            if project is None:
                raise ResourceNotFoundError("MusicProject")
            return project

    def list_projects(
        self,
        workspace_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MusicProject]:
        with self.session_factory() as session:
            repository = WorkspaceRepository(session)
            if repository.get_workspace(workspace_id) is None:
                raise ResourceNotFoundError("Workspace")
            return repository.list_projects(workspace_id, limit=limit, offset=offset)

    def update_project_metadata(
        self,
        project_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        lifecycle_status: str | None = None,
    ) -> MusicProject:
        with self.session_factory() as session, session.begin():
            repository = WorkspaceRepository(session)
            project = repository.get_project(project_id)
            if project is None:
                raise ResourceNotFoundError("MusicProject")
            if title is not None:
                normalized_title = _required_text(title, "Project 제목")
                if (
                    repository.project_title_exists(
                        project.workspace_id, normalized_title
                    )
                    and project.title != normalized_title
                ):
                    raise ResourceConflictError("Project 제목")
                project.title = normalized_title
            if description is not None:
                project.description = description.strip()
            if lifecycle_status is not None:
                project.lifecycle_status = _required_text(
                    lifecycle_status, "Project 상태"
                )
            session.flush()
        return project

    def delete_project(self, project_id: UUID) -> MusicProject:
        with self.session_factory() as session, session.begin():
            repository = WorkspaceRepository(session)
            project = repository.get_project(project_id)
            if project is None:
                raise ResourceNotFoundError("MusicProject")
            repository.soft_delete_project(project)
        return project

    def attach_asset(
        self,
        *,
        project_id: UUID,
        asset_id: UUID,
        display_order: int,
        role: str | None = None,
    ) -> ProjectAsset:
        if display_order < 0:
            raise ApplicationValidationError("display_order는 0 이상이어야 합니다.")
        normalized_role = role.strip() if role is not None else None
        try:
            with self.session_factory() as session, session.begin():
                workspace_repository = WorkspaceRepository(session)
                asset_repository = AssetRepository(session)
                project = workspace_repository.get_project(project_id)
                if project is None:
                    raise ResourceNotFoundError("MusicProject")
                asset = asset_repository.get_asset(asset_id)
                if asset is None:
                    raise ResourceNotFoundError("Asset")
                self._validate_asset_scope(project, asset)
                existing = workspace_repository.find_project_asset(
                    project_id, asset_id, include_deleted=True
                )
                if existing is not None:
                    if existing.deleted_at is None:
                        raise ResourceConflictError("ProjectAsset")
                    existing.deleted_at = None
                    existing.role = normalized_role
                    existing.display_order = display_order
                    session.flush()
                    project_asset = existing
                else:
                    project_asset = workspace_repository.add_project_asset(
                        ProjectAsset(
                            project_id=project_id,
                            asset_id=asset_id,
                            role=normalized_role,
                            display_order=display_order,
                        )
                    )
            return project_asset
        except IntegrityError:
            raise ResourceConflictError("ProjectAsset") from None

    def detach_asset(self, *, project_id: UUID, asset_id: UUID) -> ProjectAsset:
        with self.session_factory() as session, session.begin():
            repository = WorkspaceRepository(session)
            project_asset = repository.find_project_asset(project_id, asset_id)
            if project_asset is None:
                raise ResourceNotFoundError("ProjectAsset")
            repository.remove_project_asset(project_asset)
        return project_asset

    def reorder_project_asset(
        self, *, project_id: UUID, asset_id: UUID, display_order: int
    ) -> ProjectAsset:
        if display_order < 0:
            raise ApplicationValidationError("display_order는 0 이상이어야 합니다.")
        with self.session_factory() as session, session.begin():
            repository = WorkspaceRepository(session)
            project_asset = repository.find_project_asset(project_id, asset_id)
            if project_asset is None:
                raise ResourceNotFoundError("ProjectAsset")
            repository.set_project_asset_display_order(project_asset, display_order)
        return project_asset

    def list_project_assets(
        self, project_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[ProjectAsset]:
        with self.session_factory() as session:
            repository = WorkspaceRepository(session)
            if repository.get_project(project_id) is None:
                raise ResourceNotFoundError("MusicProject")
            return repository.list_project_assets(
                project_id, limit=limit, offset=offset
            )

    @staticmethod
    def _validate_asset_scope(project: MusicProject, asset: Asset) -> None:
        if (
            asset.workspace_id is not None
            and asset.workspace_id != project.workspace_id
        ):
            raise ApplicationValidationError(
                "Asset과 Project의 Workspace 범위가 일치하지 않습니다."
            )
