from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash password using Argon2id algorithm (INV-AUTH-002)."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    if not hashed_password:
        return False
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: str,
    role: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Issue signed 15-minute JWT access token (INV-AUTH-003)."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Issue signed 7-day JWT refresh token (INV-AUTH-003)."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT token signature and expiration."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError as exc:
        raise ValueError(f"Invalid token: {exc!s}") from exc
