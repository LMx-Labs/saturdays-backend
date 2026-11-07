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


async def pay_for_order(client, headers: dict, order_id: str) -> None:
    """Pay for an order the way a student does: ask for a payment, then confirm it with a valid
    Razorpay signature. Orders are invisible to the restaurant until this has happened.
    """
    import hashlib
    import hmac
    import uuid as _uuid

    from app.payment.razorpay_adapter import RazorpayAdapter

    order = (await client.get(f"/api/v1/orders/{order_id}", headers=headers)).json()
    amount = float(order["total_amount"]) - float(
        order.get("store_credit_applied") or 0
    )
    intent = await client.post(
        "/api/v1/payments/intent",
        json={"order_id": order_id, "amount": amount},
        headers=headers,
    )
    assert intent.status_code == 201, intent.text
    rzp_order = str(intent.json()["razorpay_order_id"])
    rzp_pay = f"pay_{_uuid.uuid4().hex[:10]}"
    secret = (RazorpayAdapter().key_secret or "").encode()
    signature = hmac.new(
        secret, f"{rzp_order}|{rzp_pay}".encode(), hashlib.sha256
    ).hexdigest()
    verified = await client.post(
        "/api/v1/payments/verify",
        json={
            "order_id": order_id,
            "razorpay_order_id": rzp_order,
            "razorpay_payment_id": rzp_pay,
            "razorpay_signature": signature,
        },
        headers=headers,
    )
    assert verified.status_code == 200, verified.text


# Shared with the cart robustness tests (pytest discovers fixtures in conftest).
from tests.test_cart import setup_cart_fixture  # noqa: F401
from tests.test_menu import setup_branch_and_manager  # noqa: F401
