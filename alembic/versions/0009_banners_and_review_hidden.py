"""banners table and reviews.is_hidden

The models define both, but no earlier migration created them, so on a database
built from the migrations every banner request failed ("Failed to create
banner") and review listing queried a column that did not exist.

Written with IF NOT EXISTS so it is safe on a database where either was already
added by hand.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-07

"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS banners (
            id UUID PRIMARY KEY,
            title VARCHAR(150) NOT NULL,
            image_url VARCHAR(255) NOT NULL,
            target_url VARCHAR(255),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """)
    op.execute(
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    # Intentionally empty: both objects belong to the schema the models define,
    # and dropping them could delete banners or review settings that exist
    # independently of this migration.
    pass
