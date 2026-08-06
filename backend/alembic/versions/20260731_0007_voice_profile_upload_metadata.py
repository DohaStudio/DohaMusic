"""Voice profile upload metadata and consent version.

Revision ID: 20260731_0007
Revises: 20260729_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0007"
down_revision: str | None = "20260729_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("voice_profiles") as batch:
        batch.add_column(sa.Column("display_filename", sa.String(255)))
        batch.add_column(sa.Column("mime_type", sa.String(100)))
        batch.add_column(sa.Column("size_bytes", sa.BigInteger()))
        batch.add_column(sa.Column("duration_seconds", sa.Float()))
        batch.add_column(sa.Column("sample_rate", sa.Integer()))
        batch.add_column(sa.Column("channels", sa.Integer()))
        batch.add_column(
            sa.Column("status", sa.String(20), nullable=False, server_default="READY")
        )
        batch.add_column(
            sa.Column(
                "quality_warnings", sa.JSON(), nullable=False, server_default="[]"
            )
        )
        batch.add_column(sa.Column("consent_text_version", sa.String(50)))
        batch.add_column(sa.Column("consent_confirmed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    with op.batch_alter_table("voice_profiles") as batch:
        batch.drop_column("consent_confirmed_at")
        batch.drop_column("consent_text_version")
        batch.drop_column("quality_warnings")
        batch.drop_column("status")
        batch.drop_column("channels")
        batch.drop_column("sample_rate")
        batch.drop_column("duration_seconds")
        batch.drop_column("size_bytes")
        batch.drop_column("mime_type")
        batch.drop_column("display_filename")
