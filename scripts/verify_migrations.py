import asyncio
import os
import subprocess
import sys
import uuid

import asyncpg
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from app.core.base_model import Base
from app.core.config import settings


async def verify_tables(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            actual = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
        expected = set(Base.metadata.tables)
        missing = expected - actual
        unexpected = actual - expected - {"alembic_version"}
        if missing or unexpected:
            raise RuntimeError(
                f"Migration table mismatch; missing={sorted(missing)}, unexpected={sorted(unexpected)}"
            )
    finally:
        await engine.dispose()


async def main() -> None:
    source_url = make_url(settings.DATABASE_URL)
    database_name = f"saturdays_phase7_{uuid.uuid4().hex[:12]}"
    maintenance_dsn = source_url.set(
        drivername="postgresql", database="postgres"
    ).render_as_string(hide_password=False)
    temporary_url = source_url.set(database=database_name).render_as_string(
        hide_password=False
    )
    connection = await asyncpg.connect(maintenance_dsn)
    try:
        await connection.execute(f'CREATE DATABASE "{database_name}"')
        environment = {**os.environ, "DATABASE_URL": temporary_url, "ENVIRONMENT": "test"}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=True,
            env=environment,
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "check"],
            check=True,
            env=environment,
        )
        await verify_tables(temporary_url)
        print(f"[OK] Fresh migration and {len(Base.metadata.tables)} ORM tables verified")
    finally:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
