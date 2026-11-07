"""Orders now wait for payment before the restaurant can see them

New code creates every order as PENDING_PAYMENT and moves it to PLACED when the payment is
confirmed. This migration changes no tables. It only tidies orders that already exist: ones the
old code put straight into PLACED that were never paid for (abandoned or failed checkouts) are
moved to PENDING_PAYMENT, so they leave the restaurants' screens. They are then cancelled, and any
store credit applied to them returned, the next time their student opens their orders.

The rule is deliberately cautious, so it can never hide an order someone really paid for:

* only orders still in PLACED (the kitchen has not touched them),
* only ones older than two hours (so a checkout in progress during the upgrade is left alone),
* only ones that needed real money (not ones store credit fully covered),
* and never one with a successful captured payment.

Safe to run before or after the new code is deployed, and safe to run twice.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-10

"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE orders
        SET status = 'PENDING_PAYMENT'
        WHERE status = 'PLACED'
          AND created_at < now() - interval '2 hours'
          AND (total_amount - COALESCE(store_credit_applied, 0)) > 0
          AND NOT EXISTS (
              SELECT 1
              FROM payments p
              JOIN payment_transactions t ON t.payment_id = p.id
              WHERE p.order_id = orders.id
                AND t.transaction_type = 'CAPTURED'
                AND t.status = 'SUCCESS'
          )
        """)


def downgrade() -> None:
    op.execute("UPDATE orders SET status = 'PLACED' WHERE status = 'PENDING_PAYMENT'")
