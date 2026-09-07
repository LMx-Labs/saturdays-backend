from collections.abc import Iterable
import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserClaims
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.roles import normalize_role
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserClaims:
    try:
        payload = decode_token(token)
    except ValueError:
        raise UnauthorizedError(
            message="Invalid or expired access token.",
            error_code="INVALID_ACCESS_TOKEN",
        )
    if payload.get("type") != "access":
        raise UnauthorizedError(
            message="Token provided is not an access token.",
            error_code="INVALID_TOKEN_TYPE",
        )
    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or not role:
        raise UnauthorizedError(
            message="Malformed token payload.",
            error_code="INVALID_ACCESS_TOKEN",
        )
    try:
        canonical_role = normalize_role(role)
    except ValueError:
        raise UnauthorizedError(
            message="Token contains an invalid role.",
            error_code="INVALID_ACCESS_TOKEN",
        )
    return UserClaims(sub=sub, email=payload.get("email", ""), role=canonical_role)


def get_optional_current_user(
    token: str | None = Depends(optional_oauth2_scheme),
) -> UserClaims | None:
    if token is None:
        return None
    return get_current_user(token)


def require_role(allowed_roles: Iterable[str]):
    canonical_allowed = {normalize_role(role) for role in allowed_roles}

    def role_checker(
        current_user: UserClaims = Depends(get_current_user),
    ) -> UserClaims:
        if current_user.role not in canonical_allowed:
            raise ForbiddenError(
                message=f"Access denied for role '{current_user.role}'.",
                error_code="ROLE_NOT_AUTHORIZED",
            )
        return current_user

    return role_checker


async def require_branch_access(session: AsyncSession, user_id: str, role: str, branch_id) -> None:
    from app.branch.models import Branch
    from app.brand.models import Brand
    from app.merchant.models import (
        Merchant,
        MerchantStaffMembership,
        StaffBranchAssignment,
    )

    canonical = normalize_role(role)
    if canonical == "PlatformAdmin":
        return
    if isinstance(branch_id, str):
        try:
            branch_id = uuid.UUID(branch_id)
        except ValueError:
            raise ForbiddenError(
                message="Invalid branch identifier.",
                error_code="BRANCH_ACCESS_FORBIDDEN",
            )
    user_uuid = uuid.UUID(user_id)
    owner_access = await session.scalar(
        select(Merchant.id)
        .join(Brand, Brand.merchant_id == Merchant.id)
        .join(Branch, Branch.brand_id == Brand.id)
        .where(
            Branch.id == branch_id,
            Merchant.owner_user_id == user_uuid,
            Merchant.deleted_at.is_(None),
        )
        .limit(1)
    )
    if owner_access:
        return
    staff_access = await session.scalar(
        select(MerchantStaffMembership.id)
        .join(
            StaffBranchAssignment,
            StaffBranchAssignment.membership_id == MerchantStaffMembership.id,
        )
        .where(
            MerchantStaffMembership.user_id == user_uuid,
            MerchantStaffMembership.role == canonical,
            MerchantStaffMembership.is_active.is_(True),
            StaffBranchAssignment.branch_id == branch_id,
        )
        .limit(1)
    )
    if not staff_access:
        raise ForbiddenError(
            message="You are not assigned to this branch.",
            error_code="BRANCH_ACCESS_FORBIDDEN",
        )
