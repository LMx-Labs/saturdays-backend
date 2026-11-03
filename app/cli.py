"""Operator CLI for provisioning logins directly against the database.

Public registration only creates Customers, and every staff-creation API
requires an existing PlatformAdmin. This CLI covers the two cases the API
cannot: bootstrapping the first PlatformAdmin, and (re)creating restaurant
owner logins in bulk or after a migration from the old Django/DineGuru stack.

Usage (uses DATABASE_URL from the environment / .env):

    python -m app.cli create-user --email admin@saturdays.co.in --role PlatformAdmin
    python -m app.cli create-user --email owner@diner.in --role MerchantOwner \\
        --business-name "Diner" --legal-name "Diner LLP" --fssai 12345678901234
    python -m app.cli set-password --email owner@diner.in

Passwords are prompted for (never echoed) unless --password is given.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401  (register all mappers)
from app.admin.schemas import STAFF_ACCOUNT_ROLES
from app.auth.models import User
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.merchant.models import Merchant

CLI_ROLES = (*STAFF_ACCOUNT_ROLES, "KitchenStaff")
MIN_PASSWORD_LENGTH = 8


class CliError(Exception):
    """A user-facing failure; printed without a traceback."""


async def _find_user(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(
            func.lower(User.email) == email.strip().lower(),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


def _check_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise CliError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: str,
    business_name: str | None = None,
    legal_name: str | None = None,
    fssai: str | None = None,
) -> tuple[User, Merchant | None]:
    if role not in CLI_ROLES:
        raise CliError(f"Role must be one of: {', '.join(CLI_ROLES)}.")
    if await _find_user(session, email):
        raise CliError(f"A user with email {email!r} already exists. Use set-password.")

    merchant_fields = (business_name, legal_name, fssai)
    if any(merchant_fields) and role != "MerchantOwner":
        raise CliError(
            "--business-name/--legal-name/--fssai only apply to MerchantOwner."
        )
    if any(merchant_fields) and not all(merchant_fields):
        raise CliError(
            "To create a merchant, give all of --business-name, --legal-name, --fssai."
        )

    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(_check_password(password)),
        role=role,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    merchant = None
    if all(merchant_fields):
        merchant = Merchant(
            owner_user_id=user.id,
            business_name=business_name,
            legal_entity_name=legal_name,
            fssai_license_number=fssai,
            status="ACTIVE",
        )
        session.add(merchant)

    await session.commit()
    return user, merchant


async def set_password(session: AsyncSession, *, email: str, password: str) -> User:
    user = await _find_user(session, email)
    if not user:
        raise CliError(f"No user with email {email!r}.")
    user.password_hash = hash_password(_check_password(password))
    user.is_active = True
    await session.commit()
    return user


def _password(arg: str | None) -> str:
    if arg:
        return arg
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Confirm password: "):
        raise CliError("Passwords do not match.")
    return first


async def _run(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as session:
        if args.command == "create-user":
            user, merchant = await create_user(
                session,
                email=args.email,
                password=_password(args.password),
                role=args.role,
                business_name=args.business_name,
                legal_name=args.legal_name,
                fssai=args.fssai,
            )
            print(f"Created {user.role} {user.email} (id {user.id})")
            if merchant:
                print(f"Created merchant {merchant.business_name!r} (id {merchant.id})")
            elif user.role == "MerchantOwner":
                print(
                    "No merchant created: DineGuru will prompt the owner to set up their business."
                )
        elif args.command == "set-password":
            user = await set_password(
                session, email=args.email, password=_password(args.password)
            )
            print(f"Password updated and account activated for {user.email}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description=__doc__.split("\n")[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user", help="Create a staff / restaurant login")
    create.add_argument("--email", required=True)
    create.add_argument("--role", required=True, choices=CLI_ROLES)
    create.add_argument("--password", help="Omit to be prompted (recommended)")
    create.add_argument("--business-name")
    create.add_argument("--legal-name")
    create.add_argument("--fssai")

    reset = sub.add_parser(
        "set-password", help="Reset a login's password and re-activate it"
    )
    reset.add_argument("--email", required=True)
    reset.add_argument("--password", help="Omit to be prompted (recommended)")

    args = parser.parse_args(argv)
    try:
        asyncio.run(_run(args))
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
