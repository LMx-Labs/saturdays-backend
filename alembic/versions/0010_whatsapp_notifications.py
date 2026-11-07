"""WhatsApp order updates: customer consent and a per-order message log

Customers get a `whatsapp_opt_in` flag (and the number to message), and the existing
`notifications` table learns which order and event each message was for, with a unique
index so the same message can never be sent twice for one order.

Written with IF NOT EXISTS so it is safe to run on a database where any of it was
already added by hand.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-10

"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE customer_profiles "
        "ADD COLUMN IF NOT EXISTS whatsapp_opt_in BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS whatsapp_opt_in_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE customer_profiles ADD COLUMN IF NOT EXISTS whatsapp_phone VARCHAR(20)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_customer_profiles_whatsapp_phone "
        "ON customer_profiles (whatsapp_phone)"
    )

    op.execute(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS order_id UUID REFERENCES orders (id)"
    )
    op.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS event VARCHAR(40)")
    op.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS error TEXT")
    op.execute(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ"
    )
    op.execute("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_order_id ON notifications (order_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_notifications_vendor_message_id "
        "ON notifications (vendor_message_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_order_channel_event "
        "ON notifications (order_id, channel, event) WHERE order_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notifications_order_channel_event")
    op.execute("DROP INDEX IF EXISTS ix_notifications_vendor_message_id")
    op.execute("DROP INDEX IF EXISTS ix_notifications_order_id")
    for column in ("read_at", "delivered_at", "error", "event", "order_id"):
        op.execute(f"ALTER TABLE notifications DROP COLUMN IF EXISTS {column}")
    op.execute("DROP INDEX IF EXISTS ix_customer_profiles_whatsapp_phone")
    for column in ("whatsapp_phone", "whatsapp_opt_in_at", "whatsapp_opt_in"):
        op.execute(f"ALTER TABLE customer_profiles DROP COLUMN IF EXISTS {column}")
