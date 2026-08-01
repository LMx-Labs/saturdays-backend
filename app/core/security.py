from datetime import datetime, timedelta, timezone
from typing import Optional, List, Callable
import uuid
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, Header
from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ForbiddenError

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class UserClaims(BaseModel):
    sub: str  # User ID (UUIDv7 string)
    email: str
    role: str  # Customer, KitchenStaff, BranchManager, MerchantOwner, PlatformAdmin
    merchant_id: Optional[str] = None
    branch_id: Optional[str] = None

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(claims: UserClaims, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = claims.model_dump()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(claims: UserClaims) -> str:
    return create_access_token(claims, expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))

def get_current_user(authorization: Optional[str] = Header(None)) -> UserClaims:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return UserClaims(
            sub=payload.get("sub"),
            email=payload.get("email"),
            role=payload.get("role"),
            merchant_id=payload.get("merchant_id"),
            branch_id=payload.get("branch_id")
        )
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")

def require_role(allowed_roles: List[str]):
    def role_checker(current_user: UserClaims = Depends(get_current_user)) -> UserClaims:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(f"Role '{current_user.role}' is not authorized for this operation")
        return current_user
    return role_checker
