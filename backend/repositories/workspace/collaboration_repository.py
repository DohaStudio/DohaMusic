"""Workspace Collaboration aggregate persistence operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.collaboration import (
    Approval,
    Comment,
    Favorite,
    History,
    RecordingEnrollment,
    Tag,
)
from backend.models.workspace.mixins import utc_now


class CollaborationRepository:
    """협업 Metadata aggregate를 commit 없이 현재 transaction에 반영한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_recording_enrollment(self, enrollment: RecordingEnrollment) -> RecordingEnrollment:
        self.session.add(enrollment)
        self.session.flush()
        return enrollment

    def get_recording_enrollment(
        self, enrollment_id: UUID, *, include_deleted: bool = False
    ) -> RecordingEnrollment | None:
        statement = select(RecordingEnrollment).where(
            RecordingEnrollment.recording_enrollment_id == enrollment_id
        )
        if not include_deleted:
            statement = statement.where(RecordingEnrollment.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_recording_enrollments(
        self,
        workspace_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RecordingEnrollment]:
        statement = select(RecordingEnrollment).where(
            RecordingEnrollment.workspace_id == workspace_id
        )
        if not include_deleted:
            statement = statement.where(RecordingEnrollment.deleted_at.is_(None))
        statement = (
            statement.order_by(
                RecordingEnrollment.created_at.desc(),
                RecordingEnrollment.recording_enrollment_id,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def add_tag(self, tag: Tag) -> Tag:
        self.session.add(tag)
        self.session.flush()
        return tag

    def get_tag(self, tag_id: UUID, *, include_deleted: bool = False) -> Tag | None:
        statement = select(Tag).where(Tag.tag_id == tag_id)
        if not include_deleted:
            statement = statement.where(Tag.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_tags(
        self,
        asset_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Tag]:
        statement = select(Tag).where(Tag.asset_id == asset_id)
        if not include_deleted:
            statement = statement.where(Tag.deleted_at.is_(None))
        statement = statement.order_by(Tag.name, Tag.tag_id).limit(limit).offset(offset)
        return list(self.session.scalars(statement))

    def tag_name_exists(self, asset_id: UUID, name: str, *, include_deleted: bool = False) -> bool:
        statement = select(Tag.tag_id).where(Tag.asset_id == asset_id, Tag.name == name)
        if not include_deleted:
            statement = statement.where(Tag.deleted_at.is_(None))
        return self.session.scalar(statement.limit(1)) is not None

    def find_tag(self, asset_id: UUID, name: str, *, include_deleted: bool = False) -> Tag | None:
        statement = select(Tag).where(Tag.asset_id == asset_id, Tag.name == name)
        if not include_deleted:
            statement = statement.where(Tag.deleted_at.is_(None))
        return self.session.scalar(statement.limit(1))

    def soft_delete_tag(self, tag: Tag) -> Tag:
        tag.deleted_at = utc_now()
        self.session.flush()
        return tag

    def add_comment(self, comment: Comment) -> Comment:
        self.session.add(comment)
        self.session.flush()
        return comment

    def get_comment(self, comment_id: UUID, *, include_deleted: bool = False) -> Comment | None:
        statement = select(Comment).where(Comment.comment_id == comment_id)
        if not include_deleted:
            statement = statement.where(Comment.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_comments(
        self,
        asset_version_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Comment]:
        statement = select(Comment).where(Comment.asset_version_id == asset_version_id)
        if not include_deleted:
            statement = statement.where(Comment.deleted_at.is_(None))
        statement = (
            statement.order_by(Comment.created_at, Comment.comment_id).limit(limit).offset(offset)
        )
        return list(self.session.scalars(statement))

    def soft_delete_comment(self, comment: Comment) -> Comment:
        comment.deleted_at = utc_now()
        self.session.flush()
        return comment

    def add_favorite(self, favorite: Favorite) -> Favorite:
        self.session.add(favorite)
        self.session.flush()
        return favorite

    def get_favorite(self, favorite_id: UUID, *, include_deleted: bool = False) -> Favorite | None:
        statement = select(Favorite).where(Favorite.favorite_id == favorite_id)
        if not include_deleted:
            statement = statement.where(Favorite.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_favorites(
        self,
        workspace_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Favorite]:
        statement = select(Favorite).where(Favorite.workspace_id == workspace_id)
        if not include_deleted:
            statement = statement.where(Favorite.deleted_at.is_(None))
        statement = (
            statement.order_by(Favorite.created_at, Favorite.favorite_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def favorite_exists(
        self,
        workspace_id: UUID,
        asset_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> bool:
        statement = select(Favorite.favorite_id).where(
            Favorite.workspace_id == workspace_id,
            Favorite.asset_id == asset_id,
        )
        if not include_deleted:
            statement = statement.where(Favorite.deleted_at.is_(None))
        return self.session.scalar(statement.limit(1)) is not None

    def find_favorite(
        self,
        workspace_id: UUID,
        asset_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> Favorite | None:
        statement = select(Favorite).where(
            Favorite.workspace_id == workspace_id,
            Favorite.asset_id == asset_id,
        )
        if not include_deleted:
            statement = statement.where(Favorite.deleted_at.is_(None))
        return self.session.scalar(statement.limit(1))

    def remove_favorite(self, favorite: Favorite) -> Favorite:
        favorite.deleted_at = utc_now()
        self.session.flush()
        return favorite

    def add_history(self, history: History) -> History:
        self.session.add(history)
        self.session.flush()
        return history

    def list_history(
        self,
        workspace_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[History]:
        statement = (
            select(History)
            .where(History.workspace_id == workspace_id)
            .order_by(History.created_at.desc(), History.history_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def add_approval(self, approval: Approval) -> Approval:
        self.session.add(approval)
        self.session.flush()
        return approval

    def get_approval(self, approval_id: UUID) -> Approval | None:
        return self.session.get(Approval, approval_id)

    def list_approvals(
        self,
        *,
        asset_version_id: UUID | None = None,
        recording_enrollment_id: UUID | None = None,
        model_usage_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Approval]:
        statement = select(Approval)
        if asset_version_id is not None:
            statement = statement.where(Approval.asset_version_id == asset_version_id)
        if recording_enrollment_id is not None:
            statement = statement.where(Approval.recording_enrollment_id == recording_enrollment_id)
        if model_usage_id is not None:
            statement = statement.where(Approval.model_usage_id == model_usage_id)
        statement = (
            statement.order_by(Approval.decided_at.desc(), Approval.approval_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def approval_exists(
        self,
        *,
        usage_purpose: str,
        asset_version_id: UUID | None = None,
        recording_enrollment_id: UUID | None = None,
        model_usage_id: UUID | None = None,
    ) -> bool:
        statement = select(Approval.approval_id).where(
            Approval.usage_purpose == usage_purpose,
            Approval.asset_version_id == asset_version_id,
            Approval.recording_enrollment_id == recording_enrollment_id,
            Approval.model_usage_id == model_usage_id,
        )
        return self.session.scalar(statement.limit(1)) is not None
