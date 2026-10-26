"""Database migration verification script for isolated test environments.

Supports:
- --mode fresh: creates an empty schema, runs alembic upgrade head, runs alembic check, prints 'FRESH OK'.
- --mode upgrade: seeds at 0006, inserts representative rows (merchant, branch, order),
  upgrades to head, verifies columns (is_paused, price_breakdown_snapshot, idempotency_key) and that
  rows survived, prints 'UPGRADE OK'.

Requires:
- TEST_POSTGRES_URL environment variable (or --url) pointing to a dineguru_repair_ prefixed database.
- --destructive-guard flag to confirm execution.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

REPO_ROOT = Path(__file__).resolve().parent.parent
FINAL_SCHEMA_COLUMNS = {
    "orders": {"idempotency_key", "price_breakdown_snapshot"},
    "branches": {"timezone_name"},
    "inventory_items": {"is_paused"},
    "reviews": {"is_hidden"},
    "order_reservations": {"order_id", "inventory_item_id", "released_at"},
    "banners": {"id"},
    "system_feature_flags": {"flag_key", "enabled", "value"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify database migrations for isolated PostgreSQL test databases."
    )
    parser.add_argument(
        "--mode",
        choices=["fresh", "upgrade"],
        required=True,
        help="Migration verification mode: 'fresh' or 'upgrade'.",
    )
    parser.add_argument(
        "--destructive-guard",
        action="store_true",
        default=False,
        help="Safety guard flag required to confirm destructive database operations.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Database URL (defaults to TEST_POSTGRES_URL environment variable).",
    )
    return parser.parse_args()


def run_alembic(command_args: list[str], url: str, repo_root: Path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    env["TEST_POSTGRES_URL"] = url
    cmd = [sys.executable, "-m", "alembic"] + command_args
    proc = subprocess.run(cmd, check=False, cwd=str(repo_root), env=env)
    if proc.returncode != 0:
        print(
            f"Error: alembic {' '.join(command_args)} failed with exit code {proc.returncode}",
            file=sys.stderr,
        )
        sys.exit(proc.returncode)


async def ensure_database_exists(test_url: str) -> None:
    url_obj = make_url(test_url)
    target_db = url_obj.database
    if not target_db:
        raise ValueError("Database name missing from connection URL")

    maint_url = url_obj.set(database="postgres")
    try:
        engine = create_async_engine(maint_url, isolation_level="AUTOCOMMIT")
        async with engine.connect() as conn:
            check_sql = text("SELECT 1 FROM pg_database WHERE datname = :dbname")
            res = await conn.execute(check_sql, {"dbname": target_db})
            if res.scalar() is None:
                await conn.execute(text(f'CREATE DATABASE "{target_db}"'))
        await engine.dispose()
    except (OSError, SQLAlchemyError) as exc:
        print(f"Notice: Maintenance database check bypassed: {exc}", file=sys.stderr)


async def reset_schema(url: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO CURRENT_USER;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC;"))
    await engine.dispose()


async def get_table_columns(engine: AsyncEngine, table_name: str) -> set[str]:
    async with engine.connect() as conn:
        res = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :tname"
            ),
            {"tname": table_name},
        )
        return {row[0] for row in res.fetchall()}


async def verify_head_and_columns(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            versions = (
                (await conn.execute(text("SELECT version_num FROM alembic_version")))
                .scalars()
                .all()
            )
            if versions != ["dg_20261026_05"]:
                raise RuntimeError(
                    f"Expected one final migration head; found {versions}"
                )
        for table_name, columns in FINAL_SCHEMA_COLUMNS.items():
            actual = await get_table_columns(engine, table_name)
            if not columns.issubset(actual):
                raise RuntimeError(f"Missing {table_name} columns: {columns - actual}")
    finally:
        await engine.dispose()


async def run_fresh_mode(url: str, repo_root: Path) -> None:
    await reset_schema(url)
    run_alembic(["upgrade", "head"], url, repo_root)
    run_alembic(["check"], url, repo_root)
    await verify_head_and_columns(url)
    print("FRESH OK")


async def run_upgrade_mode(url: str, repo_root: Path) -> None:
    await reset_schema(url)
    # Seed at revision 0006
    run_alembic(["upgrade", "0006"], url, repo_root)

    owner_user_id = uuid.uuid4()
    cust_user_id = uuid.uuid4()
    customer_profile_id = uuid.uuid4()
    merchant_id = uuid.uuid4()
    brand_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    menu_id = uuid.uuid4()
    category_id = uuid.uuid4()
    item1_id = uuid.uuid4()
    item2_id = uuid.uuid4()
    inv1_id = uuid.uuid4()
    inv2_id = uuid.uuid4()
    order_id = uuid.uuid4()

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        # 1. Users
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role, is_active, is_verified) "
                "VALUES (:id1, :email1, 'hash', 'MerchantOwner', true, true), "
                "(:id2, :email2, 'hash', 'Customer', true, true)"
            ),
            {
                "id1": owner_user_id,
                "email1": f"owner-{owner_user_id}@upgrade.test",
                "id2": cust_user_id,
                "email2": f"cust-{cust_user_id}@upgrade.test",
            },
        )

        # 2. Customer profile
        await conn.execute(
            text(
                "INSERT INTO customer_profiles (id, user_id, full_name, phone_number) "
                "VALUES (:id, :uid, 'Upgrade Customer', '9876543210')"
            ),
            {"id": customer_profile_id, "uid": cust_user_id},
        )

        # 3. Merchant
        await conn.execute(
            text(
                "INSERT INTO merchants (id, owner_user_id, business_name, legal_entity_name, "
                "fssai_license_number, status) "
                "VALUES (:id, :owner_id, 'Upgrade Merchant', 'Upgrade Merchant Entity', "
                "'12345678901234', 'APPROVED')"
            ),
            {"id": merchant_id, "owner_id": owner_user_id},
        )

        # 4. Brand
        await conn.execute(
            text(
                "INSERT INTO brands (id, merchant_id, name) "
                "VALUES (:id, :merchant_id, 'Upgrade Brand')"
            ),
            {"id": brand_id, "merchant_id": merchant_id},
        )

        # 5. Branch
        await conn.execute(
            text(
                "INSERT INTO branches (id, brand_id, name, address_text, is_active) "
                "VALUES (:id, :brand_id, 'Upgrade Branch', '100 Upgrade Road', true)"
            ),
            {"id": branch_id, "brand_id": brand_id},
        )

        # 6. Menu, category, items
        await conn.execute(
            text(
                "INSERT INTO menus (id, branch_id, name, is_active) "
                "VALUES (:id, :branch_id, 'Upgrade Menu', true)"
            ),
            {"id": menu_id, "branch_id": branch_id},
        )
        await conn.execute(
            text(
                "INSERT INTO menu_categories (id, menu_id, name) "
                "VALUES (:id, :menu_id, 'Upgrade Category')"
            ),
            {"id": category_id, "menu_id": menu_id},
        )
        await conn.execute(
            text(
                "INSERT INTO menu_items (id, category_id, name, base_price, is_available) "
                "VALUES (:id1, :cat_id, 'In Stock Item', 100.00, true), "
                "(:id2, :cat_id, 'Out Stock Item', 50.00, true)"
            ),
            {"id1": item1_id, "id2": item2_id, "cat_id": category_id},
        )

        # 7. Inventory items (inv1 is in stock; inv2 is out of stock to test migration 04)
        await conn.execute(
            text(
                "INSERT INTO inventory_items (id, branch_id, menu_item_id, quantity, is_in_stock) "
                "VALUES (:id1, :branch_id, :item1, 10, true), "
                "(:id2, :branch_id, :item2, 0, false)"
            ),
            {
                "id1": inv1_id,
                "id2": inv2_id,
                "branch_id": branch_id,
                "item1": item1_id,
                "item2": item2_id,
            },
        )

        # 8. Order
        addr_json = json.dumps({"address": "100 Upgrade Road", "city": "Bengaluru"})
        await conn.execute(
            text(
                "INSERT INTO orders (id, customer_profile_id, branch_id, total_amount, "
                "status, delivery_address_snapshot) "
                "VALUES (:id, :cust_id, :branch_id, 150.00, 'PLACED', "
                "CAST(:addr_json AS jsonb))"
            ),
            {
                "id": order_id,
                "cust_id": customer_profile_id,
                "branch_id": branch_id,
                "addr_json": addr_json,
            },
        )

    await engine.dispose()

    # Now upgrade all the way to head
    run_alembic(["upgrade", "head"], url, repo_root)
    await verify_head_and_columns(url)

    # Verify schema updates and row survival
    verify_engine = create_async_engine(url)
    try:
        # Check newly added columns
        inv_cols = await get_table_columns(verify_engine, "inventory_items")
        if "is_paused" not in inv_cols:
            raise RuntimeError(
                "Verification failed: 'is_paused' column missing from inventory_items"
            )

        order_cols = await get_table_columns(verify_engine, "orders")
        if "price_breakdown_snapshot" not in order_cols:
            raise RuntimeError(
                "Verification failed: 'price_breakdown_snapshot' column missing from orders"
            )
        if "idempotency_key" not in order_cols:
            raise RuntimeError(
                "Verification failed: 'idempotency_key' column missing from orders"
            )

        # Check rows survived
        async with verify_engine.connect() as conn:
            # Merchant survived
            m_res = await conn.execute(
                text("SELECT id, business_name FROM merchants WHERE id = :id"),
                {"id": merchant_id},
            )
            m_row = m_res.fetchone()
            if not m_row or m_row[1] != "Upgrade Merchant":
                raise RuntimeError(
                    "Verification failed: merchant row did not survive upgrade"
                )

            # Branch survived & received default timezone_name
            b_res = await conn.execute(
                text("SELECT id, name, timezone_name FROM branches WHERE id = :id"),
                {"id": branch_id},
            )
            b_row = b_res.fetchone()
            if not b_row or b_row[1] != "Upgrade Branch":
                raise RuntimeError(
                    "Verification failed: branch row did not survive upgrade"
                )
            if b_row[2] != "Asia/Kolkata":
                raise RuntimeError(
                    f"Verification failed: expected timezone_name 'Asia/Kolkata', got '{b_row[2]}'"
                )

            # Order survived
            o_res = await conn.execute(
                text(
                    "SELECT id, total_amount, status, price_breakdown_snapshot, idempotency_key "
                    "FROM orders WHERE id = :id"
                ),
                {"id": order_id},
            )
            o_row = o_res.fetchone()
            if (
                not o_row
                or float(o_row[1]) != 150.00
                or o_row[2] != "PLACED"
                or o_row[3] is not None
                or o_row[4] is not None
            ):
                raise RuntimeError(
                    "Verification failed: order row did not survive upgrade"
                )

            # Inventory items survived and migration 04 update logic took effect
            inv_res = await conn.execute(
                text(
                    "SELECT id, quantity, is_in_stock, is_paused FROM inventory_items "
                    "WHERE id IN (:id1, :id2)"
                ),
                {"id1": inv1_id, "id2": inv2_id},
            )
            inv_map = {row[0]: (row[1], row[2], row[3]) for row in inv_res.fetchall()}
            if inv1_id not in inv_map or inv2_id not in inv_map:
                raise RuntimeError(
                    "Verification failed: inventory items did not survive upgrade"
                )

            if inv_map[inv1_id] != (10, True, False):
                raise RuntimeError(
                    f"Verification failed: in-stock item unexpected state {inv_map[inv1_id]}"
                )
            if inv_map[inv2_id] != (0, False, True):
                raise RuntimeError(
                    f"Verification failed: out-of-stock item unexpected state {inv_map[inv2_id]}"
                )
            reservation_count = await conn.scalar(
                text("SELECT count(*) FROM order_reservations WHERE order_id = :id"),
                {"id": order_id},
            )
            if reservation_count != 0:
                raise RuntimeError(
                    "Verification failed: historical order gained a reservation"
                )
    finally:
        await verify_engine.dispose()

    run_alembic(["check"], url, repo_root)
    print("UPGRADE OK")


async def async_main() -> int:
    args = parse_args()

    if not args.destructive_guard:
        print(
            "Error: --destructive-guard must be explicitly set to run destructive migrations.",
            file=sys.stderr,
        )
        return 1

    url = args.url or os.environ.get("TEST_POSTGRES_URL")
    if not url:
        print(
            "Error: TEST_POSTGRES_URL environment variable (or --url) must be configured.",
            file=sys.stderr,
        )
        return 1

    url_obj = make_url(url)
    db_name = url_obj.database or ""
    if not db_name.startswith("dineguru_repair_"):
        print(
            f"Error: Target database '{db_name}' must start with 'dineguru_repair_'.",
            file=sys.stderr,
        )
        return 1
    if url_obj.get_backend_name() != "postgresql" or url_obj.host not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        print(
            "Error: destructive verification requires a local PostgreSQL instance.",
            file=sys.stderr,
        )
        return 1

    if args.mode == "fresh":
        await ensure_database_exists(url)
        await run_fresh_mode(url, REPO_ROOT)
    elif args.mode == "upgrade":
        await ensure_database_exists(url)
        await run_upgrade_mode(url, REPO_ROOT)

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
