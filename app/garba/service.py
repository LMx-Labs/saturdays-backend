import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, DomainInvariantError, EntityNotFoundError
from app.core.uuidv7 import uuid7
from app.garba.models import GarbaBooking, GarbaCategoryLock, GarbaInventory, GarbaTicket
from app.garba.pricing import (
    CAPACITY,
    CATEGORIES,
    DATE_CHOICES,
    ENDS_AT,
    EVENT_DATES,
    EVENT_NAME,
    HOLD_FOR,
    MAX_PER_BOOKING,
    STARTS_AT,
    TICKET_PREFIX,
    VENUE,
    attendee_count,
    prices_for,
    total_amount,
)
from app.garba.schemas import (
    GarbaAvailabilityResponse,
    GarbaBookingCreateRequest,
    GarbaBookingCreateResponse,
    GarbaBookingResponse,
    GarbaInventoryCell,
    GarbaInventoryUpdate,
    GarbaPass,
    GarbaScanResponse,
    GarbaVerifyRequest,
)
from app.payment.razorpay_adapter import RazorpayAdapter

logger = structlog.get_logger()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hold_is_active(booking: GarbaBooking, now: datetime) -> bool:
    return now - _as_utc(booking.created_at) < HOLD_FOR


def _consumes(dates: str, day: str) -> bool:
    return dates == "both" or dates == day


class GarbaService:
    def __init__(
        self,
        session: AsyncSession,
        razorpay_adapter: RazorpayAdapter | None = None,
    ):
        self.session = session
        self.razorpay_adapter = razorpay_adapter or RazorpayAdapter()

    async def availability(self) -> GarbaAvailabilityResponse:
        await self._ensure_inventory(commit=True)
        remaining: dict[str, dict[str, int]] = {}
        capacity: dict[str, dict[str, int]] = {}
        for category in CATEGORIES:
            held = await self._held_counts(category, expire=False)
            remaining[category] = {}
            capacity[category] = {}
            for day in ("17", "18"):
                row = await self._inventory_row(category, day, create=False)
                cap = row.capacity if row else CAPACITY[category]
                sold = row.sold if row else 0
                capacity[category][day] = cap
                remaining[category][day] = max(0, cap - sold - held[day])
            remaining[category]["both"] = min(
                remaining[category]["17"], remaining[category]["18"]
            )
        return GarbaAvailabilityResponse(
            name=EVENT_NAME,
            venue=VENUE,
            starts_at=STARTS_AT,
            ends_at=ENDS_AT,
            dates=dict(EVENT_DATES),
            remaining=remaining,
            capacity=capacity,
            max_per_booking=dict(MAX_PER_BOOKING),
            prices={category: prices_for(category) for category in CATEGORIES},
        )

    async def inventory(self) -> list[GarbaInventoryCell]:
        await self._ensure_inventory(commit=True)
        cells: list[GarbaInventoryCell] = []
        for category in CATEGORIES:
            held = await self._held_counts(category, expire=False)
            for day in ("17", "18"):
                row = await self._inventory_row(category, day, create=False)
                cap = row.capacity if row else CAPACITY[category]
                sold = row.sold if row else 0
                cells.append(
                    GarbaInventoryCell(
                        category=category,
                        event_date=day,
                        capacity=cap,
                        sold=sold,
                        held=held[day],
                        remaining=max(0, cap - sold - held[day]),
                    )
                )
        return cells

    async def set_capacity(self, req: GarbaInventoryUpdate) -> GarbaInventoryCell:
        await self._lock_category(req.category)
        await self._ensure_inventory()
        held = await self._held_counts(req.category, expire=True)
        row = await self._inventory_row(req.category, req.event_date, create=True)
        assert row is not None
        if req.capacity < row.sold + held[req.event_date]:
            await self.session.rollback()
            raise DomainInvariantError(
                message="Capacity cannot be lower than seats already sold or held.",
                error_code="CAPACITY_BELOW_SOLD",
            )
        row.capacity = req.capacity
        await self.session.commit()
        return GarbaInventoryCell(
            category=req.category,
            event_date=req.event_date,
            capacity=row.capacity,
            sold=row.sold,
            held=held[req.event_date],
            remaining=row.capacity - row.sold - held[req.event_date],
        )

    async def scan(self, code: str, admin_user_id: str) -> GarbaScanResponse:
        token = code.strip()
        ticket = (
            await self.session.execute(
                select(GarbaTicket).where(GarbaTicket.qr_token == token)
            )
        ).scalar_one_or_none()
        if ticket is None:
            raise EntityNotFoundError(
                message="Ticket QR code was not recognised.",
                error_code="GARBA_TICKET_NOT_FOUND",
            )
        booking = await self.session.get(GarbaBooking, ticket.booking_id)
        if booking is None or booking.status != "PAID":
            raise DomainInvariantError(
                message="This ticket is not paid.",
                error_code="GARBA_TICKET_NOT_PAID",
            )
        already = ticket.checked_in_at is not None
        if not already:
            ticket.checked_in_at = datetime.now(timezone.utc)
            await self.session.commit()
            logger.info(
                "GarbaTicketAdmitted",
                ticket_number=ticket.ticket_number,
                admin_user_id=admin_user_id,
            )
        return GarbaScanResponse(
            admitted=not already,
            already_entered=already,
            ticket_number=ticket.ticket_number,
            attendee_name=ticket.attendee_name,
            attendee_phone=ticket.attendee_phone,
            category=ticket.category,
            dates=booking.dates,
            checked_in_at=ticket.checked_in_at,
        )

    async def create_booking(
        self,
        customer_profile_id: uuid.UUID,
        req: GarbaBookingCreateRequest,
    ) -> GarbaBookingCreateResponse:
        self._check_request(req)
        amount = total_amount(req.category, req.dates, req.quantity)

        # Lock the category for the whole check-and-insert so two checkouts
        # cannot both observe the last seats and both commit.
        await self._lock_category(req.category)
        await self._ensure_inventory()
        held = await self._held_counts(req.category, expire=True)
        try:
            await self._ensure_capacity(req.category, req.dates, req.quantity, held)
        except ConflictError:
            await self.session.rollback()
            raise

        booking_id = uuid7()
        try:
            rzp_order = await self.razorpay_adapter.create_order(
                amount=amount,
                currency="INR",
                receipt=str(booking_id),
            )
        except Exception:
            await self.session.rollback()
            raise

        booking = GarbaBooking(
            id=booking_id,
            customer_profile_id=customer_profile_id,
            category=req.category,
            dates=req.dates,
            quantity=req.quantity,
            attendees=[a.model_dump() for a in req.attendees],
            amount=amount,
            currency="INR",
            status="PENDING",
            razorpay_order_id=rzp_order["id"],
            ticket_numbers=None,
        )
        self.session.add(booking)
        await self.session.commit()

        return GarbaBookingCreateResponse(
            booking_id=booking.id,
            razorpay_order_id=booking.razorpay_order_id,
            amount=amount,
            currency="INR",
            key_id=settings.RAZORPAY_KEY_ID,
            is_simulated=settings.RAZORPAY_SIMULATE,
        )

    async def verify_payment(
        self,
        booking_id: uuid.UUID,
        customer_profile_id: uuid.UUID,
        req: GarbaVerifyRequest,
    ) -> GarbaBookingResponse:
        booking = await self._owned_booking(booking_id, customer_profile_id)
        if req.razorpay_order_id != booking.razorpay_order_id:
            raise DomainInvariantError(
                message="Razorpay order does not match this booking.",
                error_code="RAZORPAY_ORDER_MISMATCH",
            )

        # Signature is checked with the server secret. Client amount, secret,
        # and ticket numbers are not accepted.
        is_valid = self.razorpay_adapter.verify_payment_signature(
            razorpay_order_id=booking.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_signature=req.razorpay_signature,
        )
        if not is_valid:
            raise DomainInvariantError(
                message="Invalid Razorpay HMAC signature.",
                error_code="INVALID_PAYMENT_SIGNATURE",
            )

        await self._lock_category(booking.category)
        await self.session.refresh(booking)

        if booking.status == "PAID":
            if booking.razorpay_payment_id == req.razorpay_payment_id:
                return await self._to_response(booking)
            raise ConflictError(
                message="This booking is already paid with a different payment.",
                error_code="BOOKING_ALREADY_PAID",
            )

        now = datetime.now(timezone.utc)
        if booking.status != "PENDING" or not _hold_is_active(booking, now):
            if booking.status == "PENDING":
                booking.status = "EXPIRED"
                await self.session.commit()
            raise DomainInvariantError(
                message="This hold has expired. Book again to take a seat.",
                error_code="HOLD_EXPIRED",
            )

        people = attendee_count(booking.category, booking.quantity)
        lock = await self._lock_category(booking.category)
        start = lock.next_ticket_number
        prefix = TICKET_PREFIX[booking.category]
        numbers = [f"{prefix}-{n:04d}" for n in range(start, start + people)]
        lock.next_ticket_number = start + people
        attendees = list(booking.attendees or [])
        for index, number in enumerate(numbers):
            person = attendees[index] if index < len(attendees) else {}
            self.session.add(
                GarbaTicket(
                    booking_id=booking.id,
                    ticket_number=number,
                    attendee_name=str(person.get("name") or ""),
                    attendee_phone=str(person.get("phone") or ""),
                    category=booking.category,
                    qr_token=secrets.token_urlsafe(24),
                )
            )
        days = ("17", "18") if booking.dates == "both" else (booking.dates,)
        for day in days:
            inventory = await self._inventory_row(booking.category, day, create=True)
            assert inventory is not None
            inventory.sold += booking.quantity
        booking.ticket_numbers = numbers
        booking.razorpay_payment_id = req.razorpay_payment_id
        booking.status = "PAID"
        await self.session.commit()

        logger.info(
            "GarbaBookingPaid",
            booking_id=str(booking.id),
            category=booking.category,
            dates=booking.dates,
            quantity=booking.quantity,
            ticket_count=len(numbers),
        )
        return await self._to_response(booking)

    async def list_paid(
        self, customer_profile_id: uuid.UUID
    ) -> list[GarbaBookingResponse]:
        stmt = (
            select(GarbaBooking)
            .where(
                GarbaBooking.customer_profile_id == customer_profile_id,
                GarbaBooking.status == "PAID",
            )
            .order_by(GarbaBooking.created_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [await self._to_response(row) for row in rows]

    def _check_request(self, req: GarbaBookingCreateRequest) -> None:
        if req.category not in CATEGORIES or req.dates not in DATE_CHOICES:
            raise DomainInvariantError(
                message="Unknown pass category or dates.",
                error_code="INVALID_GARBA_PASS",
            )
        if req.quantity > MAX_PER_BOOKING[req.category]:
            raise DomainInvariantError(
                message=(
                    f"Maximum {MAX_PER_BOOKING[req.category]} "
                    f"{req.category} passes per booking."
                ),
                error_code="MAX_QUANTITY_EXCEEDED",
            )
        expected = attendee_count(req.category, req.quantity)
        if len(req.attendees) != expected:
            raise DomainInvariantError(
                message=f"Expected {expected} attendees for this pass.",
                error_code="ATTENDEE_COUNT_MISMATCH",
            )

    async def _ensure_capacity(
        self,
        category: str,
        dates: str,
        quantity: int,
        held: dict[str, int],
    ) -> None:
        days = ("17", "18") if dates == "both" else (dates,)
        remaining: list[int] = []
        for day in days:
            row = await self._inventory_row(category, day, create=True)
            assert row is not None
            # A both-day pass needs a seat on every included date.
            remaining.append(row.capacity - row.sold - held[day])
        if min(remaining) < quantity:
            raise ConflictError(
                message="Not enough seats left for this pass.",
                error_code="SOLD_OUT",
            )

    async def _held_counts(self, category: str, *, expire: bool) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        stmt = select(GarbaBooking).where(
            GarbaBooking.category == category,
            GarbaBooking.status == "PENDING",
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        used = {"17": 0, "18": 0}
        for booking in rows:
            if not _hold_is_active(booking, now):
                if expire:
                    booking.status = "EXPIRED"
                continue
            for day in ("17", "18"):
                if _consumes(booking.dates, day):
                    used[day] += booking.quantity
        return used

    async def _ensure_inventory(self, *, commit: bool = False) -> None:
        created = False
        for category in CATEGORIES:
            for day in ("17", "18"):
                if await self._inventory_row(category, day, create=False) is None:
                    self.session.add(
                        GarbaInventory(
                            category=category,
                            event_date=day,
                            capacity=CAPACITY[category],
                            sold=0,
                        )
                    )
                    created = True
        if not created:
            return
        try:
            async with self.session.begin_nested():
                await self.session.flush()
        except IntegrityError:
            return
        if commit:
            await self.session.commit()

    async def _inventory_row(
        self, category: str, event_date: str, *, create: bool
    ) -> GarbaInventory | None:
        stmt = select(GarbaInventory).where(
            GarbaInventory.category == category,
            GarbaInventory.event_date == event_date,
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None and create:
            row = GarbaInventory(
                category=category,
                event_date=event_date,
                capacity=CAPACITY[category],
                sold=0,
            )
            self.session.add(row)
            await self.session.flush()
        return row

    async def _lock_category(self, category: str) -> GarbaCategoryLock:
        conn = await self.session.connection()
        stmt = select(GarbaCategoryLock).where(GarbaCategoryLock.category == category)
        if conn.dialect.name == "postgresql":
            stmt = stmt.with_for_update()
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = GarbaCategoryLock(category=category, next_ticket_number=1)
            self.session.add(row)
            try:
                await self.session.flush()
            except IntegrityError:
                await self.session.rollback()
                row = (await self.session.execute(stmt)).scalar_one()
            else:
                if conn.dialect.name == "postgresql":
                    row = (await self.session.execute(stmt)).scalar_one()
        return row

    async def _owned_booking(
        self, booking_id: uuid.UUID, customer_profile_id: uuid.UUID
    ) -> GarbaBooking:
        booking = await self.session.get(GarbaBooking, booking_id)
        if booking is None or booking.customer_profile_id != customer_profile_id:
            raise EntityNotFoundError(
                message="Booking not found.",
                error_code="GARBA_BOOKING_NOT_FOUND",
            )
        return booking

    async def _to_response(self, booking: GarbaBooking) -> GarbaBookingResponse:
        rows = (
            await self.session.execute(
                select(GarbaTicket)
                .where(GarbaTicket.booking_id == booking.id)
                .order_by(GarbaTicket.ticket_number)
            )
        ).scalars().all()
        return GarbaBookingResponse(
            id=booking.id,
            category=booking.category,
            dates=booking.dates,
            quantity=booking.quantity,
            attendees=booking.attendees,
            amount=int(Decimal(str(booking.amount))),
            currency=booking.currency,
            status=booking.status,
            razorpay_order_id=booking.razorpay_order_id,
            razorpay_payment_id=booking.razorpay_payment_id,
            ticket_numbers=list(booking.ticket_numbers or []),
            passes=[
                GarbaPass(
                    ticket_number=row.ticket_number,
                    name=row.attendee_name,
                    phone=row.attendee_phone,
                    qr_token=row.qr_token,
                )
                for row in rows
            ],
            created_at=booking.created_at,
        )
