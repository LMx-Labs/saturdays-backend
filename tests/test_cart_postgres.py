"""Cart concurrency and the 0007 migration, against a real PostgreSQL.

SQLite and the shared test session cannot show these problems: they need real
row locks and one database session per request. Uses the `pgserver` dev
dependency (an embedded PostgreSQL); skipped when it is not installed.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pgserver = pytest.importorskip("pgserver")
asyncpg = pytest.importorskip("asyncpg")

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.auth.models import User
from app.branch.models import Branch
from app.brand.models import Brand
from app.core.database import get_db_session
from app.core.security import hash_password
from app.customer.models import CustomerProfile
from app.main import app as fastapi_app
from app.menu.models import Menu, MenuCategory, MenuItem
from app.merchant.models import Merchant

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("pgdata")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    yield str(data_dir)
    server.cleanup()


def make_database(pg_dir: str, migrate_to: str) -> str:
    """Create a fresh database, migrate it, return its SQLAlchemy URL."""
    name = "db_" + uuid.uuid4().hex[:10]
    admin_url = f"postgresql://postgres@/postgres?host={pg_dir}"
    asyncio.run(_create_db(admin_url, name))
    url = f"postgresql+asyncpg://postgres@/{name}?host={pg_dir}"
    migrate(url, migrate_to)
    return url


async def _create_db(admin_url: str, name: str) -> None:
    conn = await asyncpg.connect(admin_url)
    try:
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


def migrate(url: str, target: str) -> None:
    env = dict(os.environ, DATABASE_URL=url, ENVIRONMENT="test")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", target],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-1500:]


def asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def seed_menu(sessions) -> dict:
    async with sessions() as s:
        owner = User(
            email="o@x.in",
            password_hash=hash_password("Password123!"),
            role="MerchantOwner",
            is_active=True,
            is_verified=True,
        )
        cust = User(
            email="c@x.in",
            password_hash=hash_password("Password123!"),
            role="Customer",
            is_active=True,
            is_verified=True,
        )
        s.add_all([owner, cust])
        await s.flush()
        s.add(CustomerProfile(user_id=cust.id, full_name="C"))
        merchant = Merchant(
            owner_user_id=owner.id,
            business_name="M",
            legal_entity_name="M",
            fssai_license_number="12345678901234",
            status="ACTIVE",
        )
        s.add(merchant)
        await s.flush()
        brand = Brand(merchant_id=merchant.id, name="B")
        s.add(brand)
        await s.flush()
        branch = Branch(brand_id=brand.id, name="Food Court", address_text="x")
        s.add(branch)
        await s.flush()
        menu = Menu(branch_id=branch.id, name="m", is_active=True)
        s.add(menu)
        await s.flush()
        cat = MenuCategory(menu_id=menu.id, name="c")
        s.add(cat)
        await s.flush()
        item = MenuItem(
            category_id=cat.id,
            name="Chicken Biryani",
            base_price=150,
            is_available=True,
        )
        s.add(item)
        await s.commit()
        return {"branch": str(branch.id), "item": str(item.id)}


@pytest.mark.parametrize("schema", ["0006", "head"])
async def test_simultaneous_adds_produce_one_cart(pg, schema):
    """Five taps in flight at once (the old code created five carts, then 500'd).

    Runs on the pre-constraint schema too: the row lock alone must prevent it,
    because migrations are applied by hand after a deploy.
    """
    url = await asyncio.to_thread(make_database, pg, schema)
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def per_request_session():
        async with sessions() as session:
            yield session

    fastapi_app.dependency_overrides[get_db_session] = per_request_session
    try:
        ids = await seed_menu(sessions)
        transport = httpx.ASGITransport(app=fastapi_app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://t"
        ) as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": "c@x.in", "password": "Password123!"},
            )
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            body = {
                "branch_id": ids["branch"],
                "menu_item_id": ids["item"],
                "quantity": 1,
            }

            responses = await asyncio.gather(
                *[
                    client.post("/api/v1/cart/items", headers=headers, json=body)
                    for _ in range(5)
                ]
            )
            assert [r.status_code for r in responses] == [200] * 5

            cart = await client.get("/api/v1/cart", headers=headers)
            assert cart.status_code == 200
            assert [
                (i["menu_item_name"], i["quantity"]) for i in cart.json()["items"]
            ] == [("Chicken Biryani", 5)]
            assert (
                await client.post("/api/v1/cart/items", headers=headers, json=body)
            ).status_code == 200
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()


async def test_migration_0007_repairs_corrupted_carts(pg):
    """Carts split by the old race are merged; healthy carts are untouched."""
    url = await asyncio.to_thread(make_database, pg, "0006")
    conn = await asyncpg.connect(asyncpg_dsn(url))
    new = uuid.uuid4
    try:
        owner, cust_a, cust_b, cust_c = new(), new(), new(), new()
        for uid, email, role in (
            (owner, "o@x", "MerchantOwner"),
            (cust_a, "a@x", "Customer"),
            (cust_b, "b@x", "Customer"),
            (cust_c, "c@x", "Customer"),
        ):
            await conn.execute(
                "insert into users (id,email,password_hash,role,is_active,is_verified) values ($1,$2,'h',$3,true,true)",
                uid,
                email,
                role,
            )
        prof_a, prof_b, prof_c = new(), new(), new()
        await conn.execute(
            "insert into customer_profiles (id,user_id,full_name) values ($1,$2,'a')",
            prof_a,
            cust_a,
        )
        await conn.execute(
            "insert into customer_profiles (id,user_id,full_name) values ($1,$2,'b')",
            prof_b,
            cust_b,
        )
        await conn.execute(
            "insert into customer_profiles (id,user_id,full_name) values ($1,$2,'c')",
            prof_c,
            cust_c,
        )
        merchant, brand, br1, br2, menu, cat = (new() for _ in range(6))
        await conn.execute(
            "insert into merchants (id,owner_user_id,business_name,legal_entity_name,fssai_license_number,status) values ($1,$2,'M','M','12345678901234','ACTIVE')",
            merchant,
            owner,
        )
        await conn.execute(
            "insert into brands (id,merchant_id,name) values ($1,$2,'B')",
            brand,
            merchant,
        )
        for br in (br1, br2):
            await conn.execute(
                "insert into branches (id,brand_id,name,address_text) values ($1,$2,'x','x')",
                br,
                brand,
            )
        await conn.execute(
            "insert into menus (id,branch_id,name,is_active) values ($1,$2,'m',true)",
            menu,
            br1,
        )
        await conn.execute(
            "insert into menu_categories (id,menu_id,name) values ($1,$2,'c')",
            cat,
            menu,
        )
        biryani, dal = new(), new()
        for item, name in ((biryani, "Biryani"), (dal, "Dal")):
            await conn.execute(
                "insert into menu_items (id,category_id,name,base_price,is_available) values ($1,$2,$3,100,true)",
                item,
                cat,
                name,
            )

        async def make_cart(profile, branch, minutes_old):
            cid = new()
            await conn.execute(
                "insert into carts (id,customer_profile_id,branch_id,created_at,updated_at) values ($1,$2,$3,now()-make_interval(mins => $4),now()-make_interval(mins => $4))",
                cid,
                profile,
                branch,
                minutes_old,
            )
            return cid

        async def add_line(cart, item, qty, minutes_old=0):
            await conn.execute(
                "insert into cart_items (id,cart_id,menu_item_id,quantity,created_at) values ($1,$2,$3,$4,now()-make_interval(mins => $5))",
                new(),
                cart,
                item,
                qty,
                minutes_old,
            )

        for minutes in (3, 2, 1):  # customer A: three carts from one burst of taps
            await add_line(await make_cart(prof_a, br1, minutes), biryani, 1)
        await add_line(
            await make_cart(prof_a, br2, 60), dal, 4
        )  # stale cart, other branch
        healthy = await make_cart(prof_b, br1, 5)  # customer B: nothing wrong
        await add_line(healthy, biryani, 2)
        await add_line(healthy, dal, 1)
        twin_lines = await make_cart(
            prof_c, br1, 1
        )  # customer C: same item on two lines
        await add_line(twin_lines, biryani, 2, minutes_old=2)
        await add_line(twin_lines, biryani, 3, minutes_old=1)
    finally:
        await conn.close()

    await asyncio.to_thread(migrate, url, "head")

    conn = await asyncpg.connect(asyncpg_dsn(url))
    try:

        async def lines(profile):
            rows = await conn.fetch(
                "select m.name, ci.quantity from cart_items ci join carts c on c.id=ci.cart_id "
                "join menu_items m on m.id=ci.menu_item_id where c.customer_profile_id=$1 order by m.name",
                profile,
            )
            return [(r["name"], r["quantity"]) for r in rows]

        assert await lines(prof_a) == [("Biryani", 3)]
        assert await lines(prof_b) == [("Biryani", 2), ("Dal", 1)]
        assert await lines(prof_c) == [("Biryani", 5)]
        assert (
            await conn.fetchval(
                "select count(*) from carts where customer_profile_id=$1", prof_a
            )
            == 1
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "insert into carts (id,customer_profile_id,branch_id) values (gen_random_uuid(),$1,$2)",
                prof_a,
                br1,
            )
    finally:
        await conn.close()
