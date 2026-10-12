import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.models as _models  # noqa: F401
from app.core.config import settings
from app.core.database import get_db_session
from app.core.exceptions import register_exception_handlers
from app.core.logging import CorrelationIdMiddleware, setup_logging

logger = structlog.get_logger()

_INSECURE_DEFAULT_SECRET = (
    "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
)


def _validate_production_settings() -> None:
    """Fail fast on unsafe configuration when running in production."""
    if not settings.is_production:
        return
    problems: list[str] = []
    if settings.JWT_SECRET_KEY == _INSECURE_DEFAULT_SECRET:
        problems.append("JWT_SECRET_KEY is the publicly known default")
    if "*" in settings.CORS_ORIGINS:
        problems.append("CORS_ORIGINS must list explicit origins, not '*'")
    if settings.RAZORPAY_SIMULATE:
        problems.append(
            "RAZORPAY_SIMULATE must be false (payouts would not move money)"
        )
    elif not (
        settings.RAZORPAY_KEY_ID
        and settings.RAZORPAY_KEY_SECRET
        and settings.RAZORPAYX_ACCOUNT_NUMBER
    ):
        problems.append(
            "RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET and RAZORPAYX_ACCOUNT_NUMBER are required"
        )
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        "Initializing Saturdays Platform",
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )
    assert settings.DATABASE_URL is not None, "DATABASE_URL must be configured"
    assert settings.SECRET_KEY is not None, "SECRET_KEY must be configured"
    _validate_production_settings()
    scheduler_task = None
    if settings.PAYOUT_SCHEDULER_ENABLED:
        from app.payout.scheduler import run_daily_payout_scheduler

        scheduler_task = asyncio.create_task(run_daily_payout_scheduler())
    yield
    if scheduler_task:
        scheduler_task.cancel()
    logger.info("Shutting down Saturdays Platform")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Middleware order matters: the last one added is outermost. CORS must wrap
# everything (including the 500 fallback in CorrelationIdMiddleware) so that
# error responses still carry Access-Control-* headers.
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=settings.cors_allow_credentials_effective,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
    max_age=600,
)

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.branch.router import router as branch_router
from app.brand.router import router as brand_router
from app.cart.router import router as cart_router
from app.checkout.router import router as checkout_router
from app.coupon.router import router as coupon_router
from app.credit.router import router as credit_router
from app.customer.router import router as customer_router
from app.garba.router import router as garba_router
from app.inventory.router import router as inventory_router
from app.kitchen.router import router as kitchen_router
from app.menu.router import router as menu_router
from app.merchant.router import router as merchant_router
from app.notification.router import router as notification_router
from app.order.router import router as order_router
from app.payment.router import router as payment_router
from app.payout.router import router as payout_router
from app.review.router import router as review_router
from app.search.router import router as search_router
from app.subscription.router import router as subscription_router

register_exception_handlers(app)

app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(cart_router, prefix=settings.API_V1_STR)
app.include_router(checkout_router, prefix=settings.API_V1_STR)
app.include_router(coupon_router, prefix=settings.API_V1_STR)
app.include_router(credit_router, prefix=settings.API_V1_STR)
app.include_router(customer_router, prefix=settings.API_V1_STR)
app.include_router(garba_router, prefix=settings.API_V1_STR)
app.include_router(inventory_router, prefix=settings.API_V1_STR)
app.include_router(kitchen_router, prefix=settings.API_V1_STR)
app.include_router(notification_router, prefix=settings.API_V1_STR)
app.include_router(order_router, prefix=settings.API_V1_STR)
app.include_router(review_router, prefix=settings.API_V1_STR)
app.include_router(subscription_router, prefix=settings.API_V1_STR)
app.include_router(menu_router, prefix=settings.API_V1_STR)
app.include_router(brand_router, prefix=settings.API_V1_STR)
app.include_router(branch_router, prefix=settings.API_V1_STR)
app.include_router(merchant_router, prefix=settings.API_V1_STR)
app.include_router(payment_router, prefix=settings.API_V1_STR)
app.include_router(payout_router, prefix=settings.API_V1_STR)
app.include_router(search_router, prefix=settings.API_V1_STR)


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
    except Exception as e:  # noqa: BLE001
        logger.error("Readiness check database connection failure", error=str(e))
        return {"status": "not_ready", "database": "disconnected"}
