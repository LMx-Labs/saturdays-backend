"""Add short_location and google_maps_url to branches.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column("short_location", sa.String(100), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column("google_maps_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("branches", "google_maps_url")
    op.drop_column("branches", "short_location")
