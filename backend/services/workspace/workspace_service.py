"""Workspace와 MusicProject application use case."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.cursor_pagination import (
    CURSOR_SORT,
    PROJECT_ASSET_CURSOR_SORT,
    CursorCodec,
    filter_fingerprint,
)
from backend.core.exceptions import (
    ApplicationValidationError,
    CursorConfigurationError,
    InvalidLimitError,
    InvalidStateError,
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


@dataclass(frozen=True, slots=True)
class BootstrapWorkspaceResult:
    workspace: Workspace
    created: bool


PageItemT = TypeVar("PageItemT")


@dataclass(frozen=True, slots=True)
class CursorPage(Generic[PageItemT]):
    items: tuple[PageItemT, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


class WorkspaceService:
    """Workspace aggregate의 transaction 경계를 소유한다."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        cursor_codec: CursorCodec | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.cursor_codec = cursor_codec

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

    def bootstrap_default_workspace(
        self,
        *,
        owner_id: UUID,
        name: str,
    ) -> BootstrapWorkspaceResult:
        """단일 owner의 기본 Workspace를 한 transaction에서 생성하거나 재사용한다."""

        normalized_name = _required_text(name, "Workspace 이름")
        try:
            with self.session_factory() as session, session.begin():
                repository = WorkspaceRepository(session)
                active_workspaces = repository.list_workspaces(limit=2)
                if len(active_workspaces) > 1:
                    raise InvalidStateError("기본 Workspace")
                if active_workspaces:
                    if active_workspaces[0].owner_id != owner_id:
                        raise ResourceConflictError("기본 Workspace owner")
                    result = BootstrapWorkspaceResult(
                        workspace=active_workspaces[0],
                        created=False,
                    )
                else:
                    workspace = repository.add_workspace(
                        Workspace(
                            owner_id=owner_id,
                            name=normalized_name,
                            lifecycle_status="active",
                        )
                    )
                    result = BootstrapWorkspaceResult(
                        workspace=workspace,
                        created=True,
                    )
            return result
        except IntegrityError:
            raise ResourceConflictError("기본 Workspace") from None

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

    def list_workspace_page(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
        owner_id: UUID | None = None,
    ) -> CursorPage[Workspace]:
        _validate_page_limit(limit)
        codec = self._require_cursor_codec()
        filter_hash = filter_fingerprint(
            {
                "include_deleted": False,
                "owner_id": str(owner_id) if owner_id is not None else None,
                "sort": CURSOR_SORT,
            }
        )
        position = (
            codec.decode(
                cursor,
                expected_resource="workspace",
                expected_filter_hash=filter_hash,
                expected_limit=limit,
            )
            if cursor is not None
            else None
        )
        with self.session_factory() as session:
            rows = WorkspaceRepository(session).list_workspaces_after(
                owner_id=owner_id,
                last_created_at=(position.last_created_at if position else None),
                last_id=(position.last_id if position else None),
                limit=limit + 1,
            )
        return self._build_page(
            rows,
            resource="workspace",
            id_attribute="workspace_id",
            filter_hash=filter_hash,
            limit=limit,
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

    def list_project_page(
        self,
        workspace_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[MusicProject]:
        _validate_page_limit(limit)
        codec = self._require_cursor_codec()
        filter_hash = filter_fingerprint(
            {
                "include_deleted": False,
                "sort": CURSOR_SORT,
                "workspace_id": str(workspace_id),
            }
        )
        position = (
            codec.decode(
                cursor,
                expected_resource="project",
                expected_filter_hash=filter_hash,
                expected_limit=limit,
            )
            if cursor is not None
            else None
        )
        with self.session_factory() as session:
            repository = WorkspaceRepository(session)
            if repository.get_workspace(workspace_id) is None:
                raise ResourceNotFoundError("Workspace")
            rows = repository.list_projects_after(
                workspace_id,
                last_created_at=(position.last_created_at if position else None),
                last_id=(position.last_id if position else None),
                limit=limit + 1,
            )
        return self._build_page(
            rows,
            resource="project",
            id_attribute="project_id",
            filter_hash=filter_hash,
            limit=limit,
        )

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
            workspace_repository = WorkspaceRepository(session)
            asset_repository = AssetRepository(session)
            if workspace_repository.get_project(project_id) is None:
                raise ResourceNotFoundError("MusicProject")
            if asset_repository.get_asset(asset_id) is None:
                raise ResourceNotFoundError("Asset")
            project_asset = workspace_repository.find_project_asset(
                project_id, asset_id
            )
            if project_asset is None:
                raise ResourceNotFoundError("ProjectAsset")
            workspace_repository.remove_project_asset(project_asset)
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

    def list_project_asset_page(
        self,
        project_id: UUID,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[ProjectAsset]:
        """ProjectAsset 연결을 display order ASC cursor page로 조회한다."""

        _validate_page_limit(limit)
        codec = self._require_cursor_codec()
        filter_hash = filter_fingerprint(
            {
                "include_deleted": False,
                "project_id": str(project_id),
                "sort": PROJECT_ASSET_CURSOR_SORT,
            }
        )
        position = (
            codec.decode_project_asset(
                cursor,
                expected_filter_hash=filter_hash,
                expected_limit=limit,
            )
            if cursor is not None
            else None
        )
        with self.session_factory() as session:
            repository = WorkspaceRepository(session)
            if repository.get_project(project_id) is None:
                raise ResourceNotFoundError("MusicProject")
            rows = repository.list_project_assets_after(
                project_id,
                last_display_order=(position.last_display_order if position else None),
                last_id=(position.last_id if position else None),
                limit=limit + 1,
            )
        return self._build_project_asset_page(
            rows,
            filter_hash=filter_hash,
            limit=limit,
        )

    def _require_cursor_codec(self) -> CursorCodec:
        if self.cursor_codec is None:
            raise CursorConfigurationError()
        return self.cursor_codec

    def _build_page(
        self,
        rows: list[PageItemT],
        *,
        resource: Literal["workspace", "project"],
        id_attribute: str,
        filter_hash: str,
        limit: int,
    ) -> CursorPage[PageItemT]:
        has_more = len(rows) > limit
        items = tuple(rows[:limit])
        next_cursor = None
        if has_more:
            last_item = items[-1]
            next_cursor = self._require_cursor_codec().encode(
                resource=resource,
                last_created_at=getattr(last_item, "created_at"),
                last_id=getattr(last_item, id_attribute),
                filter_hash=filter_hash,
                limit=limit,
            )
        return CursorPage(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
            limit=limit,
        )

    def _build_project_asset_page(
        self,
        rows: list[ProjectAsset],
        *,
        filter_hash: str,
        limit: int,
    ) -> CursorPage[ProjectAsset]:
        has_more = len(rows) > limit
        items = tuple(rows[:limit])
        next_cursor = None
        if has_more:
            last_item = items[-1]
            next_cursor = self._require_cursor_codec().encode_project_asset(
                last_display_order=last_item.display_order,
                last_id=last_item.project_asset_id,
                filter_hash=filter_hash,
                limit=limit,
            )
        return CursorPage(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
            limit=limit,
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


def _validate_page_limit(limit: object) -> None:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise InvalidLimitError()
