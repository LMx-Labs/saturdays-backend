import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.admin.models import SystemFeatureFlag
from app.brand.models import Brand
from app.checkout.repository import CheckoutRepositoryInterface
from app.checkout.schemas import (
    CheckoutIssue,
    CheckoutItemSummary,
    CheckoutValidateRequest,
    CheckoutValidationResponse,
)
from app.core.config import get_settings
from app.coupon.repository import CouponRepository, CouponRepositoryInterface
from app.coupon.service import CouponService, CouponServiceInterface
from app.customer.repository import CustomerRepository
from app.menu.models import MenuCategory, MenuItem
from app.merchant.models import Merchant
from app.order.pricing import PriceLine, calculate_price


class CheckoutServiceInterface(ABC):
    """Abstract service interface for pre-order checkout validation."""

    @abstractmethod
    async def validate_checkout(
        self, user_id: str, req: CheckoutValidateRequest
    ) -> CheckoutValidationResponse:
        """Validate pre-order checkout session and calculate order financial totals."""


class CheckoutService(CheckoutServiceInterface):
    """Concrete implementation of CheckoutServiceInterface."""

    def __init__(
        self,
        session: AsyncSession,
        checkout_repo: CheckoutRepositoryInterface,
        coupon_service: CouponServiceInterface | None = None,
    ) -> None:
        self.session = session
        self.checkout_repo = checkout_repo
        if coupon_service is None:
            coupon_repo: CouponRepositoryInterface = CouponRepository(session)
            customer_repo = CustomerRepository(session)
            self.coupon_service: CouponServiceInterface = CouponService(
                session=session, coupon_repo=coupon_repo, customer_repo=customer_repo
            )
        else:
            self.coupon_service = coupon_service

    async def validate_checkout(
        self, user_id: str, req: CheckoutValidateRequest
    ) -> CheckoutValidationResponse:
        user_uuid = uuid.UUID(user_id)
        issues: list[CheckoutIssue] = []

        # 1. Validate Customer
        profile = await self.checkout_repo.get_customer_profile(user_uuid)
        if not profile:
            issues.append(
                CheckoutIssue(
                    code="CUSTOMER_NOT_FOUND",
                    message="Customer profile not found for authenticated user.",
                )
            )
            cust_id = ""
        else:
            cust_id = str(profile.id)

        # 2. Validate Cart
        try:
            cart_uuid = uuid.UUID(req.cart_id)
        except ValueError:
            issues.append(
                CheckoutIssue(code="INVALID_UUID", message="Invalid cart UUID format.")
            )
            return self._build_empty_response(req.cart_id, issues)

        cart = await self.checkout_repo.get_cart_with_items(cart_uuid)
        if not cart or not cart.items:
            issues.append(
                CheckoutIssue(code="CART_EMPTY", message="Cart is empty or not found.")
            )
            return self._build_empty_response(req.cart_id, issues, cust_id)
        if str(cart.customer_profile_id) != cust_id:
            issues.append(
                CheckoutIssue(
                    code="CART_ACCESS_FORBIDDEN",
                    message="Cart does not belong to this customer.",
                )
            )
            return self._build_empty_response(req.cart_id, issues, cust_id)

        branch_uuid = cart.branch_id
        maintenance = await self.session.get(
            SystemFeatureFlag, "EMERGENCY_MAINTENANCE_MODE"
        )
        if get_settings().EMERGENCY_MAINTENANCE_MODE or (
            maintenance and maintenance.enabled
        ):
            issues.append(
                CheckoutIssue(
                    code="MAINTENANCE_MODE",
                    message="Checkout is paused for maintenance.",
                )
            )
        branch = await self.checkout_repo.get_branch(branch_uuid)

        # 3. Validate Branch & Restaurant Availability (INV-CHK-001)
        if not branch:
            issues.append(
                CheckoutIssue(
                    code="BRANCH_NOT_FOUND",
                    message="Associated restaurant branch not found.",
                )
            )
            branch_name = "Unknown Branch"
        else:
            branch_name = branch.name
            if not branch.is_active:
                issues.append(
                    CheckoutIssue(
                        code="BRANCH_OFFLINE",
                        message=f"Branch '{branch.name}' is currently offline.",
                    )
                )

            # Operating hours check
            current_time = (
                datetime.now(UTC)
                .astimezone(ZoneInfo(branch.timezone_name))
                .time()
                .replace(tzinfo=None)
            )
            opening, closing = branch.opening_time, branch.closing_time
            is_open = (
                True
                if opening == closing
                else (
                    opening <= current_time <= closing
                    if opening < closing
                    else current_time >= opening or current_time <= closing
                )
            )
            if not is_open:
                issues.append(
                    CheckoutIssue(
                        code="BRANCH_CLOSED",
                        message=f"Branch '{branch.name}' is closed. Operating hours: {branch.opening_time} to {branch.closing_time}.",
                    )
                )

        # 3b. Validate Merchant approval status
        if branch:
            approved = await self.session.scalar(
                select(Merchant.id)
                .join(Brand, Brand.merchant_id == Merchant.id)
                .where(Brand.id == branch.brand_id, Merchant.status == "APPROVED")
            )
            if approved is None:
                issues.append(
                    CheckoutIssue(
                        code="MERCHANT_NOT_APPROVED",
                        message="This restaurant is not currently accepting orders.",
                    )
                )

        # 4. Validate Kitchen Station
        kitchen = await self.checkout_repo.get_kitchen_for_branch(branch_uuid)
        kitchen_id_str = str(kitchen.id) if kitchen else None
        if not kitchen:
            issues.append(
                CheckoutIssue(
                    code="KITCHEN_UNAVAILABLE",
                    message="No active kitchen station available at this branch.",
                )
            )

        # 5. Inventory Availability Verification (INV-0005) & Subtotal Math
        item_summaries: list[CheckoutItemSummary] = []
        price_lines: list[PriceLine] = []

        for cart_item in cart.items:
            # Fetch menu item details with category and menu to align with final admission
            stmt_menu = (
                select(MenuItem)
                .options(joinedload(MenuItem.category).joinedload(MenuCategory.menu))
                .where(
                    MenuItem.id == cart_item.menu_item_id,
                    MenuItem.deleted_at.is_(None),
                )
            )
            res_menu = await self.session.execute(stmt_menu)
            menu_item = res_menu.scalar_one_or_none()

            if (
                not menu_item
                or not menu_item.is_available
                or menu_item.category is None
                or menu_item.category.deleted_at is not None
                or menu_item.category.menu is None
                or menu_item.category.menu.deleted_at is not None
                or not menu_item.category.menu.is_active
            ):
                issues.append(
                    CheckoutIssue(
                        code="ITEM_UNAVAILABLE",
                        message=f"Menu item '{cart_item.menu_item_id}' is unavailable.",
                    )
                )
                unit_price = 0.0
                item_name = menu_item.name if menu_item else "Unavailable Item"
                is_avail = False
            elif menu_item.category.menu.branch_id != branch_uuid:
                issues.append(
                    CheckoutIssue(
                        code="CROSS_BRANCH_ORDER_VIOLATION",
                        message=f"Menu item '{cart_item.menu_item_id}' does not belong to branch '{branch_uuid}'.",
                    )
                )
                unit_price = 0.0
                item_name = menu_item.name
                is_avail = False
            else:
                unit_price = float(menu_item.base_price)
                item_name = menu_item.name
                is_avail = True

                # Check inventory pause and stock status (is_paused gates before stock)
                inv = await self.checkout_repo.get_inventory_item(
                    branch_uuid, cart_item.menu_item_id
                )
                if inv is None:
                    is_avail = False
                    issues.append(
                        CheckoutIssue(
                            code="INSUFFICIENT_STOCK",
                            message=f"Item '{menu_item.name}' has no inventory record or insufficient stock.",
                        )
                    )
                elif inv.is_paused:
                    is_avail = False
                    issues.append(
                        CheckoutIssue(
                            code="ITEM_PAUSED",
                            message=f"Item '{menu_item.name}' is temporarily paused and cannot be ordered.",
                        )
                    )
                elif not inv.is_in_stock or inv.quantity < cart_item.quantity:
                    is_avail = False
                    issues.append(
                        CheckoutIssue(
                            code="INSUFFICIENT_STOCK",
                            message=f"Item '{menu_item.name}' has insufficient stock (available: {inv.quantity}, requested: {cart_item.quantity}).",
                        )
                    )

            line_subtotal = round(unit_price * cart_item.quantity, 2)
            price_lines.append(
                PriceLine(
                    unit_price=Decimal(str(unit_price)), quantity=cart_item.quantity
                )
            )

            item_summaries.append(
                CheckoutItemSummary(
                    menu_item_id=str(cart_item.menu_item_id),
                    name=item_name,
                    unit_price=unit_price,
                    quantity=cart_item.quantity,
                    subtotal=line_subtotal,
                    is_available=is_avail,
                )
            )

        # 6. Validate Coupon & Discount Amount
        price = calculate_price(price_lines)
        subtotal = float(price.subtotal)
        discount_amount = float(price.discount)
        if req.coupon_code:
            issues.append(
                CheckoutIssue(
                    code="COUPON_NOT_SUPPORTED",
                    message="Coupon checkout is unavailable until discounts are applied to saved orders.",
                )
            )

        # 7. Financial Calculations (Tax, Delivery Fee, Final Payable)
        # The production order persists item subtotal only. No tax or fee policy
        # has been configured, so a quote must not advertise extra charges.
        tax_amount = float(price.tax)
        delivery_fee = float(price.delivery_fee)
        final_payable = float(price.total)

        is_valid = len(issues) == 0

        return CheckoutValidationResponse(
            is_valid=is_valid,
            customer_id=cust_id,
            branch_id=str(branch_uuid),
            branch_name=branch_name,
            kitchen_id=kitchen_id_str,
            cart_id=str(cart.id),
            subtotal=subtotal,
            tax_amount=tax_amount,
            delivery_fee=delivery_fee,
            discount_amount=discount_amount,
            final_payable_amount=final_payable,
            coupon_code=req.coupon_code,
            items=item_summaries,
            issues=issues,
        )

    def _build_empty_response(
        self,
        cart_id: str,
        issues: list[CheckoutIssue],
        customer_id: str = "",
    ) -> CheckoutValidationResponse:
        return CheckoutValidationResponse(
            is_valid=False,
            customer_id=customer_id,
            branch_id="",
            branch_name="",
            kitchen_id=None,
            cart_id=cart_id,
            subtotal=0.0,
            tax_amount=0.0,
            delivery_fee=0.0,
            discount_amount=0.0,
            final_payable_amount=0.0,
            coupon_code=None,
            items=[],
            issues=issues,
        )
