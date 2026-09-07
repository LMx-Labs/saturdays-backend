"""add banners and canonical user roles

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ROLES = "'Customer', 'KitchenStaff', 'BranchManager', 'MerchantOwner', 'PlatformAdmin'"


def upgrade() -> None:
    op.execute("UPDATE users SET role = 'PlatformAdmin' WHERE role = 'Admin'")
    op.create_check_constraint("ck_users_role_canonical", "users", f"role IN ({ROLES})")
    op.create_table(
        "banners",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("image_url", sa.String(length=255), nullable=False),
        sa.Column("target_url", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("banners")
    op.drop_constraint("ck_users_role_canonical", "users", type_="check")
