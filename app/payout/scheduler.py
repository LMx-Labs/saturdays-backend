"""Daily payout trigger.

Runs inside the API process when ``PAYOUT_SCHEDULER_ENABLED=true``. Several replicas
may run it safely (advisory lock + per-order uniqueness + Razorpay idempotency).
Alternatively leave it off and run ``python -m app.payout.scheduler`` from cron.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppException
from app.payout.service import PayoutService

logger = structlog.get_logger()


async def run_once() -> None:
    async with AsyncSessionLocal() as session:
        try:
            result = await PayoutService(session).run_daily_payouts()
            logger.info(
                "DailyPayoutRunCompleted",
                payout_date=str(result.payout_date),
                merchants_paid=result.merchants_paid,
                total_net_amount=result.total_net_amount,
                skipped=len(result.skipped),
            )
        except AppException as exc:
            logger.warning("DailyPayoutRunSkipped", reason=exc.message)


def _seconds_until_next_run(now: datetime) -> float:
    target = now.replace(
        hour=settings.PAYOUT_SCHEDULE_HOUR_UTC, minute=0, second=0, microsecond=0
    )
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def run_daily_payout_scheduler() -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_run(datetime.now(UTC)))
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("DailyPayoutRunCrashed")


if __name__ == "__main__":
    asyncio.run(run_once())
