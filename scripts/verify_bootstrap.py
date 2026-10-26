"""Exercise first-admin creation and repeat refusal on a disposable local database."""

import asyncio
import os
import secrets
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> int:
    url = os.environ.get("TEST_POSTGRES_URL", "")
    parsed = make_url(url)
    if (
        parsed.get_backend_name() != "postgresql"
        or parsed.host not in {"localhost", "127.0.0.1", "::1"}
        or not (parsed.database or "").startswith("dineguru_repair_")
    ):
        raise RuntimeError(
            "Bootstrap verification requires a local disposable PostgreSQL database"
        )

    email = f"bootstrap-{uuid.uuid4()}@example.invalid"
    env = os.environ.copy()
    env.update(
        DATABASE_URL=url,
        BOOTSTRAP_ADMIN_EMAIL=email,
        BOOTSTRAP_ADMIN_PASSWORD=secrets.token_urlsafe(24),
    )
    command = [sys.executable, "-m", "scripts.bootstrap_admin"]
    first = await asyncio.create_subprocess_exec(
        *command,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    first_stdout, _ = await first.communicate()
    if first.returncode != 0 or b"Initial PlatformAdmin created." not in first_stdout:
        raise RuntimeError("First-admin bootstrap did not create the account")

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT role, is_active, is_verified FROM users WHERE email = :email"
                    ),
                    {"email": email},
                )
            ).one_or_none()
            if row is None or tuple(row) != ("PlatformAdmin", True, True):
                raise RuntimeError("Bootstrap account was not persisted correctly")
    finally:
        await engine.dispose()

    repeat = await asyncio.create_subprocess_exec(
        *command,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, repeat_stderr = await repeat.communicate()
    if repeat.returncode == 0 or b"already exists" not in repeat_stderr:
        raise RuntimeError("Repeat bootstrap was not refused")
    print("BOOTSTRAP OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
