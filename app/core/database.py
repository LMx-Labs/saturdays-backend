from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Pool sizing for Cloud Run + Neon
# concurrency=8, max_instances=5 → peak = 5*(5+5)=50 connections
# Neon free tier cap ≈100; this leaves headroom for alembic migrations.
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    future=True,
    pool_pre_ping=True,   # detects stale connections after Neon idle-disconnect
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,    # recycle before Neon's idle-timeout disconnects the socket
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base SQLAlchemy 2.0 Declarative Model."""


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing asynchronous database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
