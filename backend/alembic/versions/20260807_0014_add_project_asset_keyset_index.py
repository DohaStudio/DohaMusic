"""ProjectAsset display order keyset 조회용 partial Index를 추가한다.

Revision ID: 20260807_0014
Revises: 20260807_0013
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_0014"
down_revision: str | None = "20260807_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """활성 ProjectAsset의 display order keyset Index만 추가한다."""

    op.create_index(
        "ix_project_assets_active_keyset",
        "project_assets",
        ["project_id", "display_order", "project_asset_id"],
        unique=False,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """이번 revision에서 추가한 Index만 제거한다."""

    op.drop_index(
        "ix_project_assets_active_keyset",
        table_name="project_assets",
    )
