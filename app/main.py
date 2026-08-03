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
    yield
    logger.info("Shutting down Saturdays Platform")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.branch.router import router as branch_router
from app.brand.router import router as brand_router
from app.cart.router import router as cart_router
from app.checkout.router import router as checkout_router
from app.coupon.router import router as coupon_router
from app.customer.router import router as customer_router
from app.inventory.router import router as inventory_router
from app.kitchen.router import router as kitchen_router
from app.menu.router import router as menu_router
from app.merchant.router import router as merchant_router
from app.notification.router import router as notification_router
from app.order.router import router as order_router
from app.payment.router import router as payment_router
from app.review.router import router as review_router
from app.search.router import router as search_router
from app.subscription.router import router as subscription_router

register_exception_handlers(app)

app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(cart_router, prefix=settings.API_V1_STR)
app.include_router(checkout_router, prefix=settings.API_V1_STR)
app.include_router(coupon_router, prefix=settings.API_V1_STR)
app.include_router(customer_router, prefix=settings.API_V1_STR)
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
