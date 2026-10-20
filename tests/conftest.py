from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.auth.models import User
from app.core.database import Base, get_db_session
from app.core.security import hash_password
from app.main import app as fastapi_app

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _get_test_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db_session] = _get_test_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


async def seed_user_login(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    password: str = "Password123!",
    role: str = "Customer",
    branch_id=None,
    is_active: bool = True,
) -> dict:
    """Insert a user and log in. Public /auth/register only creates Customers."""
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=role,
        branch_id=branch_id,
        is_active=is_active,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login.json().get("access_token") if login.status_code == 200 else None
    return {
        "user": user,
        "login": login,
        "access_token": token,
        "headers": {"Authorization": f"Bearer {token}"} if token else {},
    }
