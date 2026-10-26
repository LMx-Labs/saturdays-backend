"""Create previously missing banners and durable operational flags.

Revision ID: dg_20261026_02
Revises: dg_20261026_01
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "dg_20261026_02"
down_revision = "dg_20261026_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "banners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("image_url", sa.String(255), nullable=False),
        sa.Column("target_url", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "system_feature_flags",
        sa.Column("flag_key", sa.String(100), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("value", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("system_feature_flags")
    op.drop_table("banners")
