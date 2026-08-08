"""Owner scope Asset keyset 조회용 full Index를 추가한다.

Revision ID: 20260808_0015
Revises: 20260807_0014
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260808_0015"
down_revision: str | None = "20260807_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """활성 Asset의 Owner·Workspace keyset Index만 추가한다."""

    op.create_index(
        "ix_assets_owner_active_keyset",
        "assets",
        ["owner_id", "deleted_at", "created_at", "asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_assets_owner_workspace_active_keyset",
        "assets",
        ["owner_id", "workspace_id", "deleted_at", "created_at", "asset_id"],
        unique=False,
    )


def downgrade() -> None:
    """이번 revision에서 추가한 Asset Index만 역순으로 제거한다."""

    op.drop_index(
        "ix_assets_owner_workspace_active_keyset",
        table_name="assets",
    )
    op.drop_index(
        "ix_assets_owner_active_keyset",
        table_name="assets",
    )
