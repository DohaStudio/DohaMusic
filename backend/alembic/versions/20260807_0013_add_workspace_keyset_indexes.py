"""Workspace와 MusicProject keyset 조회용 복합 Index를 추가한다.

Revision ID: 20260807_0013
Revises: 20260806_0012
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260807_0013"
down_revision: str | None = "20260806_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """활성 Workspace와 Project keyset 정렬을 지원하는 Index만 추가한다."""
    op.create_index(
        "ix_workspaces_active_keyset",
        "workspaces",
        ["deleted_at", "created_at", "workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspaces_owner_active_keyset",
        "workspaces",
        ["owner_id", "deleted_at", "created_at", "workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_music_projects_workspace_active_keyset",
        "music_projects",
        ["workspace_id", "deleted_at", "created_at", "project_id"],
        unique=False,
    )


def downgrade() -> None:
    """이번 revision에서 추가한 복합 Index만 역순으로 제거한다."""
    op.drop_index(
        "ix_music_projects_workspace_active_keyset",
        table_name="music_projects",
    )
    op.drop_index(
        "ix_workspaces_owner_active_keyset",
        table_name="workspaces",
    )
    op.drop_index(
        "ix_workspaces_active_keyset",
        table_name="workspaces",
    )
