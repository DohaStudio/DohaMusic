"""Workspace, MusicProject와 ProjectAsset persistence operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.mixins import utc_now
from backend.models.workspace.workspace import MusicProject, ProjectAsset, Workspace


class WorkspaceRepository:
    """Workspace aggregate를 commit 없이 현재 transaction에 반영한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_workspace(self, workspace: Workspace) -> Workspace:
        self.session.add(workspace)
        self.session.flush()
        return workspace

    def get_workspace(
        self, workspace_id: UUID, *, include_deleted: bool = False
    ) -> Workspace | None:
        statement = select(Workspace).where(Workspace.workspace_id == workspace_id)
        if not include_deleted:
            statement = statement.where(Workspace.deleted_at.is_(None))
        return self.session.scalar(statement)

    def get_workspace_for_owner(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> Workspace | None:
        statement = select(Workspace).where(
            Workspace.workspace_id == workspace_id,
            Workspace.owner_id == owner_id,
        )
        if not include_deleted:
            statement = statement.where(Workspace.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_workspaces(
        self,
        *,
        owner_id: UUID | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Workspace]:
        statement = select(Workspace)
        if owner_id is not None:
            statement = statement.where(Workspace.owner_id == owner_id)
        if not include_deleted:
            statement = statement.where(Workspace.deleted_at.is_(None))
        statement = (
            statement.order_by(Workspace.created_at.desc(), Workspace.workspace_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def workspace_name_exists(
        self, owner_id: UUID, name: str, *, include_deleted: bool = False
    ) -> bool:
        statement = select(Workspace.workspace_id).where(
            Workspace.owner_id == owner_id,
            Workspace.name == name,
        )
        if not include_deleted:
            statement = statement.where(Workspace.deleted_at.is_(None))
        return self.session.scalar(statement.limit(1)) is not None

    def soft_delete_workspace(self, workspace: Workspace) -> Workspace:
        workspace.deleted_at = utc_now()
        self.session.flush()
        return workspace

    def add_project(self, project: MusicProject) -> MusicProject:
        self.session.add(project)
        self.session.flush()
        return project

    def get_project(
        self, project_id: UUID, *, include_deleted: bool = False
    ) -> MusicProject | None:
        statement = select(MusicProject).where(MusicProject.project_id == project_id)
        if not include_deleted:
            statement = statement.where(MusicProject.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_projects(
        self,
        workspace_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MusicProject]:
        statement = select(MusicProject).where(
            MusicProject.workspace_id == workspace_id
        )
        if not include_deleted:
            statement = statement.where(MusicProject.deleted_at.is_(None))
        statement = (
            statement.order_by(MusicProject.created_at.desc(), MusicProject.project_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def project_title_exists(
        self,
        workspace_id: UUID,
        title: str,
        *,
        include_deleted: bool = False,
    ) -> bool:
        statement = select(MusicProject.project_id).where(
            MusicProject.workspace_id == workspace_id,
            MusicProject.title == title,
        )
        if not include_deleted:
            statement = statement.where(MusicProject.deleted_at.is_(None))
        return self.session.scalar(statement.limit(1)) is not None

    def soft_delete_project(self, project: MusicProject) -> MusicProject:
        project.deleted_at = utc_now()
        self.session.flush()
        return project

    def add_project_asset(self, project_asset: ProjectAsset) -> ProjectAsset:
        self.session.add(project_asset)
        self.session.flush()
        return project_asset

    def get_project_asset(
        self, project_asset_id: UUID, *, include_deleted: bool = False
    ) -> ProjectAsset | None:
        statement = select(ProjectAsset).where(
            ProjectAsset.project_asset_id == project_asset_id
        )
        if not include_deleted:
            statement = statement.where(ProjectAsset.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_project_assets(
        self,
        project_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProjectAsset]:
        statement = select(ProjectAsset).where(ProjectAsset.project_id == project_id)
        if not include_deleted:
            statement = statement.where(ProjectAsset.deleted_at.is_(None))
        statement = (
            statement.order_by(
                ProjectAsset.display_order, ProjectAsset.project_asset_id
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def project_asset_exists(
        self,
        project_id: UUID,
        asset_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> bool:
        statement = select(ProjectAsset.project_asset_id).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_id == asset_id,
        )
        if not include_deleted:
            statement = statement.where(ProjectAsset.deleted_at.is_(None))
        return self.session.scalar(statement.limit(1)) is not None

    def remove_project_asset(self, project_asset: ProjectAsset) -> ProjectAsset:
        project_asset.deleted_at = utc_now()
        self.session.flush()
        return project_asset

    def set_project_asset_display_order(
        self, project_asset: ProjectAsset, display_order: int
    ) -> ProjectAsset:
        project_asset.display_order = display_order
        self.session.flush()
        return project_asset
