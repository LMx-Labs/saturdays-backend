"""Admin endpoints for editing subscription plan configurations.

Registered at /api/v1/admin/subscription-plans
Admins can update plan names, prices, features, order quotas,
commission rates, and sync plans to Razorpay — all without code changes.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import require_role
from app.auth.schemas import UserClaims
from app.core.database import get_db_session
from app.subscription.models import SubscriptionPlanConfig
from app.subscription.razorpay_service import create_razorpay_plan

router = APIRouter(prefix="/admin/subscription-plans", tags=["Admin — Subscription Plans"])
logger = structlog.get_logger()

# Defaults seeded when the config row doesn't exist yet
_PLAN_DEFAULTS: dict[str, dict[str, Any]] = {
    "BASIC": {
        "name": "Campus Starter",
        "price_monthly": 999,
        "max_orders_per_day": 40,
        "max_branches": 1,
        "commission_rate_pct": 7.0,
        "razorpay_plan_id": "plan_U4Nmn66KGNB4wb",
        "features": [
            "1 Campus Branch Outlet",
            "Up to 40 orders/day",
            "7% Platform Commission Rate",
            "Kitchen Kanban Board",
            "Digital Menu & Inventory",
            "Daily Automated Settlements",
        ],
    },
    "PROFESSIONAL": {
        "name": "Growth Multi-Store",
        "price_monthly": 2499,
        "max_orders_per_day": 100,
        "max_branches": 5,
        "commission_rate_pct": 5.0,
        "razorpay_plan_id": "plan_U4NmnN6qIC7Ytd",
        "features": [
            "Up to 5 Campus Branch Outlets",
            "Up to 100 orders/day",
            "Reduced 5% Commission Rate",
            "Multi-Kitchen Prep Stations",
            "Automated Out-of-Stock Alerting",
            "Priority Merchant Support",
        ],
    },
    "ENTERPRISE": {
        "name": "Campus Franchise",
        "price_monthly": 4999,
        "max_orders_per_day": 200,
        "max_branches": 20,
        "commission_rate_pct": 3.5,
        "razorpay_plan_id": "plan_U4Nmnd0UVUlajZ",
        "features": [
            "Up to 20 Campus Outlets",
            "Up to 200 orders/day",
            "Lowest 3.5% Commission Rate",
            "Dedicated Account Manager",
            "Custom Multi-Brand Catalog",
            "API & POS Integration Support",
        ],
    },
}

VALID_TIERS = frozenset(_PLAN_DEFAULTS.keys())


class PlanConfigUpdateRequest(BaseModel):
    name: str | None = None
    price_monthly: int | None = None
    max_orders_per_day: int | None = None
    max_branches: int | None = None
    commission_rate_pct: float | None = None
    features: list[str] | None = None
    offer_text: str | None = None
    razorpay_plan_id: str | None = None
    is_active: bool | None = None
    trial_days: int | None = None


class PlanConfigResponse(BaseModel):
    tier: str
    name: str
    price_monthly: int
    max_orders_per_day: int
    max_branches: int
    commission_rate_pct: float
    features: list[str]
    offer_text: str | None
    razorpay_plan_id: str | None
    is_active: bool
    trial_days: int
    updated_at: datetime


async def _get_or_seed(session: AsyncSession, tier: str) -> SubscriptionPlanConfig:
    """Get plan config row, auto-seeding defaults if missing."""
    result = await session.execute(
        select(SubscriptionPlanConfig).where(SubscriptionPlanConfig.tier == tier)
    )
    config = result.scalar_one_or_none()
    if config is None:
        defaults = _PLAN_DEFAULTS[tier]
        config = SubscriptionPlanConfig(
            tier=tier,
            name=defaults["name"],
            price_monthly=defaults["price_monthly"],
            max_orders_per_day=defaults["max_orders_per_day"],
            max_branches=defaults["max_branches"],
            commission_rate_pct=defaults["commission_rate_pct"],
            features=defaults["features"],
            is_active=True,
            trial_days=7,
        )
        session.add(config)
        await session.flush()
    return config


def _to_response(c: SubscriptionPlanConfig) -> PlanConfigResponse:
    return PlanConfigResponse(
        tier=c.tier,
        name=c.name,
        price_monthly=c.price_monthly,
        max_orders_per_day=c.max_orders_per_day,
        max_branches=c.max_branches,
        commission_rate_pct=float(c.commission_rate_pct),
        features=c.features or [],
        offer_text=c.offer_text,
        razorpay_plan_id=c.razorpay_plan_id,
        is_active=c.is_active,
        trial_days=c.trial_days,
        updated_at=c.updated_at,
    )


@router.get("", response_model=list[PlanConfigResponse], status_code=status.HTTP_200_OK)
async def list_plan_configs(
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
    session: AsyncSession = Depends(get_db_session),
) -> list[PlanConfigResponse]:
    """Return all 3 plan configs; seeds defaults for any missing tier."""
    configs = []
    for tier in ("BASIC", "PROFESSIONAL", "ENTERPRISE"):
        configs.append(await _get_or_seed(session, tier))
    await session.commit()
    return [_to_response(c) for c in configs]


@router.patch("/{tier}", response_model=PlanConfigResponse, status_code=status.HTTP_200_OK)
async def update_plan_config(
    tier: str,
    req: PlanConfigUpdateRequest,
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
    session: AsyncSession = Depends(get_db_session),
) -> PlanConfigResponse:
    """Admin edits any plan field — name, features, price, quota, commission, etc."""
    tier = tier.upper()
    if tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tier '{tier}'")

    config = await _get_or_seed(session, tier)

    if req.name is not None:
        config.name = req.name
    if req.price_monthly is not None:
        config.price_monthly = req.price_monthly
    if req.max_orders_per_day is not None:
        config.max_orders_per_day = req.max_orders_per_day
    if req.max_branches is not None:
        config.max_branches = req.max_branches
    if req.commission_rate_pct is not None:
        config.commission_rate_pct = req.commission_rate_pct
    if req.features is not None:
        config.features = req.features
    if req.offer_text is not None:
        config.offer_text = req.offer_text
    if req.razorpay_plan_id is not None:
        config.razorpay_plan_id = req.razorpay_plan_id
    if req.is_active is not None:
        config.is_active = req.is_active
    if req.trial_days is not None:
        config.trial_days = req.trial_days

    config.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(config)
    logger.info("Plan config updated by admin", tier=tier)
    return _to_response(config)


@router.post(
    "/{tier}/sync-razorpay",
    response_model=PlanConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def sync_plan_to_razorpay(
    tier: str,
    _: UserClaims = Depends(require_role(["PlatformAdmin", "Admin", "admin"])),
    session: AsyncSession = Depends(get_db_session),
) -> PlanConfigResponse:
    """Creates a Razorpay plan for this tier and stores its plan_id."""
    tier = tier.upper()
    if tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tier '{tier}'")

    config = await _get_or_seed(session, tier)
    try:
        rzp_plan = await create_razorpay_plan(tier, config.price_monthly, config.name)
        config.razorpay_plan_id = rzp_plan.get("id")
        config.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(config)
        logger.info("Razorpay plan synced", tier=tier, rzp_id=config.razorpay_plan_id)
    except Exception as exc:
        logger.error("Razorpay plan sync failed", tier=tier, error=str(exc))
        raise HTTPException(
            status_code=502, detail=f"Razorpay API error: {exc!s}"
        ) from exc

    return _to_response(config)
