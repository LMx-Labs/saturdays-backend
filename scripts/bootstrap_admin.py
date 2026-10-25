"""One-time operator setup for the first PlatformAdmin.

Requires BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD and DATABASE_URL in
the process environment. Never prints the password or creates demo users.
"""

import asyncio
import os
import sys

from sqlalchemy import func, select

from app.auth.models import User
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password


async def main() -> int:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not os.environ.get("DATABASE_URL") or "@" not in email or len(password) < 12:
        print(
            "Set DATABASE_URL, BOOTSTRAP_ADMIN_EMAIL and a password of at least 12 characters.",
            file=sys.stderr,
        )
        return 2
    async with AsyncSessionLocal() as session:
        admin_exists = await session.scalar(
            select(User.id)
            .where(User.role == "PlatformAdmin", User.deleted_at.is_(None))
            .limit(1)
        )
        if admin_exists is not None:
            print("A PlatformAdmin already exists; bootstrap refused.", file=sys.stderr)
            return 1
        email_exists = await session.scalar(
            select(User.id)
            .where(func.lower(User.email) == email, User.deleted_at.is_(None))
            .limit(1)
        )
        if email_exists is not None:
            print("Email is already assigned; bootstrap refused.", file=sys.stderr)
            return 1
        session.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role="PlatformAdmin",
                is_active=True,
                is_verified=True,
            )
        )
        await session.commit()
    print("Initial PlatformAdmin created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
