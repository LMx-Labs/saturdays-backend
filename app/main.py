from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.core.logging import setup_logging, CorrelationIdMiddleware
from app.core.exceptions import register_exception_handlers

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup structured logging
    setup_logging()
    
    # Startup Configuration Validation
    logger.info("Initializing Saturdays Platform", project=settings.PROJECT_NAME, version=settings.VERSION, environment=settings.ENVIRONMENT)
    assert settings.DATABASE_URL is not None, "DATABASE_URL must be configured"
    assert settings.SECRET_KEY is not None, "SECRET_KEY must be configured"
    
    yield
    logger.info("Shutting down Saturdays Platform")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Correlation ID Middleware
app.add_middleware(CorrelationIdMiddleware)

# Register Global Exception Handlers
register_exception_handlers(app)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

@app.get("/health/live", tags=["Health"])
async def liveness_check():
    return {"status": "alive"}

@app.get("/health/ready", tags=["Health"])
async def readiness_check(session: AsyncSession = Depends(get_db_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error("Readiness check database connection failure", error=str(e))
        return {"status": "not_ready", "database": "disconnected"}
