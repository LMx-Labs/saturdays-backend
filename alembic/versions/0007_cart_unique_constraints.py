"""cart uniqueness: one cart per customer, one line per menu item

Simultaneous "add to cart" requests used to create several carts (or several
lines for the same item) for one customer. Every later cart request for that
customer then failed with HTTP 500 (MultipleResultsFound). This migration

  1. merges existing duplicates, keeping the most recently updated cart and
     adding up the quantities of duplicated lines (each duplicate was one
     tap of "add", so the sum is what the customer asked for), then
  2. adds the unique constraints that make duplicates impossible.

Duplicate carts that belong to a different branch than the surviving cart are
dropped rather than merged: a cart can only hold one branch's items.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-01

"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Merge duplicate carts into the most recently updated one per customer.
    op.execute(sa.text("""
            CREATE TEMPORARY TABLE _cart_survivor ON COMMIT DROP AS
            SELECT DISTINCT ON (customer_profile_id)
                   customer_profile_id, id AS survivor_id, branch_id AS survivor_branch
            FROM carts
            ORDER BY customer_profile_id, updated_at DESC, created_at DESC, id DESC
            """))
    op.execute(sa.text("""
            UPDATE cart_items ci
            SET cart_id = s.survivor_id
            FROM carts c
            JOIN _cart_survivor s ON s.customer_profile_id = c.customer_profile_id
            WHERE ci.cart_id = c.id
              AND c.id <> s.survivor_id
              AND c.branch_id = s.survivor_branch
            """))
    # Items still attached to a duplicate cart (other branch) go with it: the
    # cart_items.cart_id foreign key is ON DELETE CASCADE.
    op.execute(sa.text("""
            DELETE FROM carts c
            USING _cart_survivor s
            WHERE c.customer_profile_id = s.customer_profile_id
              AND c.id <> s.survivor_id
            """))

    # 2. Merge duplicate lines: keep the oldest, give it the summed quantity.
    op.execute(sa.text("""
            UPDATE cart_items ci
            SET quantity = r.total
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER w AS rn,
                       SUM(quantity) OVER (PARTITION BY cart_id, menu_item_id) AS total
                FROM cart_items
                WINDOW w AS (PARTITION BY cart_id, menu_item_id ORDER BY created_at, id)
            ) r
            WHERE ci.id = r.id AND r.rn = 1 AND ci.quantity <> r.total
            """))
    op.execute(sa.text("""
            DELETE FROM cart_items
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY cart_id, menu_item_id ORDER BY created_at, id
                           ) AS rn
                    FROM cart_items
                ) ranked
                WHERE rn > 1
            )
            """))

    # 3. Make duplicates impossible from now on.
    op.create_unique_constraint(
        "uq_carts_customer_profile_id", "carts", ["customer_profile_id"]
    )
    op.create_unique_constraint(
        "uq_cart_items_cart_menu_item", "cart_items", ["cart_id", "menu_item_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_cart_items_cart_menu_item", "cart_items", type_="unique")
    op.drop_constraint("uq_carts_customer_profile_id", "carts", type_="unique")
