"""Workspace 협업 Metadata application use case."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    ApplicationValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from backend.models.workspace import (
    Approval,
    AssetType,
    Comment,
    Favorite,
    History,
    ModelUsage,
    RecordingEnrollment,
    Tag,
)
from backend.repositories.workspace import (
    AssetRepository,
    CollaborationRepository,
    WorkspaceRepository,
)


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ApplicationValidationError(f"{field_name}은(는) 비어 있을 수 없습니다.")
    return normalized


class CollaborationService:
    """Tag·Comment·Favorite·History·Approval·Enrollment use case."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def create_tag(self, *, asset_id: UUID, name: str, created_by: UUID) -> Tag:
        normalized_name = _required_text(name, "Tag 이름")
        try:
            with self.session_factory() as session, session.begin():
                asset_repository = AssetRepository(session)
                repository = CollaborationRepository(session)
                if asset_repository.get_asset(asset_id) is None:
                    raise ResourceNotFoundError("Asset")
                existing = repository.find_tag(
                    asset_id, normalized_name, include_deleted=True
                )
                if existing is not None:
                    if existing.deleted_at is None:
                        raise ResourceConflictError("Tag")
                    existing.deleted_at = None
                    session.flush()
                    tag = existing
                else:
                    tag = repository.add_tag(
                        Tag(
                            asset_id=asset_id,
                            name=normalized_name,
                            created_by=created_by,
                        )
                    )
            return tag
        except IntegrityError:
            raise ResourceConflictError("Tag") from None

    def list_tags(
        self, asset_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Tag]:
        with self.session_factory() as session:
            if AssetRepository(session).get_asset(asset_id) is None:
                raise ResourceNotFoundError("Asset")
            return CollaborationRepository(session).list_tags(
                asset_id, limit=limit, offset=offset
            )

    def delete_tag(self, tag_id: UUID) -> Tag:
        with self.session_factory() as session, session.begin():
            repository = CollaborationRepository(session)
            tag = repository.get_tag(tag_id)
            if tag is None:
                raise ResourceNotFoundError("Tag")
            repository.soft_delete_tag(tag)
        return tag

    def create_comment(
        self, *, asset_version_id: UUID, created_by: UUID, body: str
    ) -> Comment:
        normalized_body = _required_text(body, "Comment 본문")
        with self.session_factory() as session, session.begin():
            if AssetRepository(session).get_asset_version(asset_version_id) is None:
                raise ResourceNotFoundError("AssetVersion")
            comment = CollaborationRepository(session).add_comment(
                Comment(
                    asset_version_id=asset_version_id,
                    created_by=created_by,
                    body=normalized_body,
                )
            )
        return comment

    def list_comments(
        self, asset_version_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Comment]:
        with self.session_factory() as session:
            if AssetRepository(session).get_asset_version(asset_version_id) is None:
                raise ResourceNotFoundError("AssetVersion")
            return CollaborationRepository(session).list_comments(
                asset_version_id, limit=limit, offset=offset
            )

    def delete_comment(self, comment_id: UUID) -> Comment:
        with self.session_factory() as session, session.begin():
            repository = CollaborationRepository(session)
            comment = repository.get_comment(comment_id)
            if comment is None:
                raise ResourceNotFoundError("Comment")
            repository.soft_delete_comment(comment)
        return comment

    def add_favorite(self, *, workspace_id: UUID, asset_id: UUID) -> Favorite:
        try:
            with self.session_factory() as session, session.begin():
                workspace_repository = WorkspaceRepository(session)
                asset_repository = AssetRepository(session)
                repository = CollaborationRepository(session)
                if workspace_repository.get_workspace(workspace_id) is None:
                    raise ResourceNotFoundError("Workspace")
                asset = asset_repository.get_asset(asset_id)
                if asset is None:
                    raise ResourceNotFoundError("Asset")
                if (
                    asset.workspace_id is not None
                    and asset.workspace_id != workspace_id
                ):
                    raise ApplicationValidationError(
                        "Favorite Asset의 Workspace 범위가 다릅니다."
                    )
                existing = repository.find_favorite(
                    workspace_id, asset_id, include_deleted=True
                )
                if existing is not None:
                    if existing.deleted_at is None:
                        return existing
                    existing.deleted_at = None
                    session.flush()
                    favorite = existing
                else:
                    favorite = repository.add_favorite(
                        Favorite(workspace_id=workspace_id, asset_id=asset_id)
                    )
            return favorite
        except IntegrityError:
            raise ResourceConflictError("Favorite") from None

    def list_favorites(
        self, workspace_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Favorite]:
        with self.session_factory() as session:
            if WorkspaceRepository(session).get_workspace(workspace_id) is None:
                raise ResourceNotFoundError("Workspace")
            return CollaborationRepository(session).list_favorites(
                workspace_id, limit=limit, offset=offset
            )

    def remove_favorite(self, favorite_id: UUID) -> Favorite:
        with self.session_factory() as session, session.begin():
            repository = CollaborationRepository(session)
            favorite = repository.get_favorite(favorite_id)
            if favorite is None:
                raise ResourceNotFoundError("Favorite")
            repository.remove_favorite(favorite)
        return favorite

    def record_history(
        self,
        *,
        workspace_id: UUID,
        actor_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before_snapshot: dict[str, Any] | None = None,
        after_snapshot: dict[str, Any] | None = None,
    ) -> History:
        with self.session_factory() as session, session.begin():
            if WorkspaceRepository(session).get_workspace(workspace_id) is None:
                raise ResourceNotFoundError("Workspace")
            history = CollaborationRepository(session).add_history(
                History(
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    entity_type=_required_text(entity_type, "History Entity 유형"),
                    entity_id=entity_id,
                    action=_required_text(action, "History Action"),
                    before_snapshot=(
                        dict(before_snapshot) if before_snapshot is not None else None
                    ),
                    after_snapshot=(
                        dict(after_snapshot) if after_snapshot is not None else None
                    ),
                )
            )
        return history

    def list_history(
        self, workspace_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[History]:
        with self.session_factory() as session:
            if WorkspaceRepository(session).get_workspace(workspace_id) is None:
                raise ResourceNotFoundError("Workspace")
            return CollaborationRepository(session).list_history(
                workspace_id, limit=limit, offset=offset
            )

    def create_approval(
        self,
        *,
        usage_purpose: str,
        status: str,
        approved_by: UUID,
        evidence_id: str,
        decided_at: datetime,
        asset_version_id: UUID | None = None,
        recording_enrollment_id: UUID | None = None,
        model_usage_id: UUID | None = None,
    ) -> Approval:
        targets = [asset_version_id, recording_enrollment_id, model_usage_id]
        if sum(target is not None for target in targets) != 1:
            raise ApplicationValidationError(
                "Approval 대상은 정확히 하나만 지정해야 합니다."
            )
        with self.session_factory() as session, session.begin():
            repository = CollaborationRepository(session)
            if asset_version_id is not None:
                if AssetRepository(session).get_asset_version(asset_version_id) is None:
                    raise ResourceNotFoundError("AssetVersion")
            elif recording_enrollment_id is not None:
                if repository.get_recording_enrollment(recording_enrollment_id) is None:
                    raise ResourceNotFoundError("RecordingEnrollment")
            if model_usage_id is not None:
                if session.get(ModelUsage, model_usage_id) is None:
                    raise ResourceNotFoundError("ModelUsage")
            approval = repository.add_approval(
                Approval(
                    asset_version_id=asset_version_id,
                    recording_enrollment_id=recording_enrollment_id,
                    model_usage_id=model_usage_id,
                    usage_purpose=_required_text(usage_purpose, "승인 목적"),
                    status=_required_text(status, "승인 상태"),
                    approved_by=approved_by,
                    evidence_id=_required_text(evidence_id, "승인 근거 ID"),
                    decided_at=decided_at,
                )
            )
        return approval

    def list_approvals(
        self,
        *,
        asset_version_id: UUID | None = None,
        recording_enrollment_id: UUID | None = None,
        model_usage_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Approval]:
        with self.session_factory() as session:
            return CollaborationRepository(session).list_approvals(
                asset_version_id=asset_version_id,
                recording_enrollment_id=recording_enrollment_id,
                model_usage_id=model_usage_id,
                limit=limit,
                offset=offset,
            )

    def create_recording_enrollment(
        self,
        *,
        workspace_id: UUID,
        recording_asset_version_id: UUID,
        status: str,
        consent_policy_version: str,
        consent_evidence_id: str,
        created_by: UUID,
    ) -> RecordingEnrollment:
        try:
            with self.session_factory() as session, session.begin():
                if WorkspaceRepository(session).get_workspace(workspace_id) is None:
                    raise ResourceNotFoundError("Workspace")
                asset_repository = AssetRepository(session)
                version = asset_repository.get_asset_version(recording_asset_version_id)
                if version is None:
                    raise ResourceNotFoundError("Recording AssetVersion")
                asset = asset_repository.get_asset(version.asset_id)
                if asset is None or asset.asset_type is not AssetType.RECORDING:
                    raise ApplicationValidationError(
                        "Enrollment에는 Recording AssetVersion이 필요합니다."
                    )
                if asset.workspace_id != workspace_id:
                    raise ApplicationValidationError(
                        "Enrollment의 Workspace 범위가 일치하지 않습니다."
                    )
                enrollment = CollaborationRepository(session).add_recording_enrollment(
                    RecordingEnrollment(
                        workspace_id=workspace_id,
                        recording_asset_version_id=recording_asset_version_id,
                        status=_required_text(status, "Enrollment 상태"),
                        consent_policy_version=_required_text(
                            consent_policy_version, "Consent 정책 version"
                        ),
                        consent_evidence_id=_required_text(
                            consent_evidence_id, "Consent 증적 ID"
                        ),
                        created_by=created_by,
                    )
                )
            return enrollment
        except IntegrityError:
            raise ResourceConflictError("RecordingEnrollment") from None

    def get_recording_enrollment(self, enrollment_id: UUID) -> RecordingEnrollment:
        with self.session_factory() as session:
            enrollment = CollaborationRepository(session).get_recording_enrollment(
                enrollment_id
            )
            if enrollment is None:
                raise ResourceNotFoundError("RecordingEnrollment")
            return enrollment

    def list_recording_enrollments(
        self, workspace_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[RecordingEnrollment]:
        with self.session_factory() as session:
            if WorkspaceRepository(session).get_workspace(workspace_id) is None:
                raise ResourceNotFoundError("Workspace")
            return CollaborationRepository(session).list_recording_enrollments(
                workspace_id, limit=limit, offset=offset
            )
