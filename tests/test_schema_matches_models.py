"""Guard: a database built from the migrations must have everything the models expect.

Two bugs got to production because a model was added without a migration (the
`banners` table, the `reviews.is_hidden` column). This builds a real PostgreSQL
from the migrations and compares it with the models, so the next one fails here
instead. Skipped when `pgserver` is not installed.
"""

import asyncio

import pytest

pgserver = pytest.importorskip("pgserver")
asyncpg = pytest.importorskip("asyncpg")

import app.models  # noqa: F401  (register every model)
from app.core.database import Base
from tests.test_cart_postgres import asyncpg_dsn, make_database, migrate


@pytest.fixture(scope="module")
def pg(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("pgdata")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    yield str(data_dir)
    server.cleanup()


async def _live_schema(url: str) -> tuple[set[str], dict[str, set[str]]]:
    conn = await asyncpg.connect(asyncpg_dsn(url))
    try:
        tables = {
            r["table_name"]
            for r in await conn.fetch(
                "select table_name from information_schema.tables where table_schema='public'"
            )
        }
        columns: dict[str, set[str]] = {}
        for r in await conn.fetch(
            "select table_name, column_name from information_schema.columns "
            "where table_schema='public'"
        ):
            columns.setdefault(r["table_name"], set()).add(r["column_name"])
        return tables, columns
    finally:
        await conn.close()


async def test_migrations_match_models(pg):
    url = await asyncio.to_thread(make_database, pg, "head")
    tables, columns = await _live_schema(url)

    missing_tables = sorted(set(Base.metadata.tables) - tables)
    missing_columns = {
        name: sorted({c.name for c in table.columns} - columns.get(name, set()))
        for name, table in Base.metadata.tables.items()
        if name in tables and {c.name for c in table.columns} - columns.get(name, set())
    }
    assert not missing_tables, f"Models with no migration: {missing_tables}"
    assert not missing_columns, f"Model columns with no migration: {missing_columns}"


async def test_0009_safe_if_objects_exist(pg):
    """Production may have had these added by hand; the migration must not fail on that."""
    url = await asyncio.to_thread(make_database, pg, "0008")
    conn = await asyncpg.connect(asyncpg_dsn(url))
    try:
        await conn.execute(
            "create table banners (id uuid primary key, title varchar(150) not null, "
            "image_url varchar(255) not null, target_url varchar(255), "
            "is_active boolean not null default true, display_order integer not null default 0, "
            "created_at timestamptz not null default now())"
        )
        await conn.execute(
            "insert into banners (id, title, image_url) values (gen_random_uuid(), 'keep me', 'x')"
        )
        await conn.execute(
            "alter table reviews add column is_hidden boolean not null default false"
        )
    finally:
        await conn.close()

    await asyncio.to_thread(migrate, url, "head")  # must not raise

    conn = await asyncpg.connect(asyncpg_dsn(url))
    try:
        assert await conn.fetchval("select title from banners") == "keep me"
    finally:
        await conn.close()
