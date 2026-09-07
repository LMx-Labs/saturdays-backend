import argparse
import asyncio
import getpass

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, select

from app.auth.models import User
from app.core.database import AsyncSessionLocal, engine
from app.core.roles import Role
from app.core.security import hash_password


async def create_platform_admin(email: str, password: str, promote: bool) -> None:
    normalized_email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                func.lower(User.email) == normalized_email,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user:
            if user.role != Role.PLATFORM_ADMIN.value and not promote:
                raise RuntimeError("User exists with another role. Re-run with --promote.")
            user.role = Role.PLATFORM_ADMIN.value
            user.password_hash = hash_password(password)
            user.is_active = True
            user.is_verified = True
        else:
            session.add(
                User(
                    email=normalized_email,
                    password_hash=hash_password(password),
                    role=Role.PLATFORM_ADMIN.value,
                    is_active=True,
                    is_verified=True,
                )
            )
        await session.commit()
    await engine.dispose()
    print(f"[OK] Platform Admin ready: {normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create the first Platform Admin through an explicit operator command."
    )
    parser.add_argument("email")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 8:
        raise SystemExit("Password must contain at least 8 characters.")
    asyncio.run(create_platform_admin(args.email, password, args.promote))


if __name__ == "__main__":
    main()
