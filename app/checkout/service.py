import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.checkout.repository import CheckoutRepositoryInterface
from app.checkout.schemas import (
    CheckoutIssue,
    CheckoutItemSummary,
    CheckoutValidateRequest,
    CheckoutValidationResponse,
)
from app.coupon.repository import CouponRepository, CouponRepositoryInterface
from app.coupon.schemas import CouponValidateRequest as CouponCodeValidateRequest
from app.coupon.service import CouponService, CouponServiceInterface
from app.customer.repository import CustomerRepository
from app.menu.models import MenuItem


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

        branch_uuid = cart.branch_id
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
            current_time = datetime.now(UTC).time()
            if current_time < branch.opening_time or current_time > branch.closing_time:
                issues.append(
                    CheckoutIssue(
                        code="BRANCH_CLOSED",
                        message=f"Branch '{branch.name}' is closed. Operating hours: {branch.opening_time} to {branch.closing_time}.",
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
        subtotal = 0.0

        for cart_item in cart.items:
            # Fetch menu item details
            stmt_menu = select(MenuItem).where(
                MenuItem.id == cart_item.menu_item_id,
                MenuItem.deleted_at.is_(None),
            )
            res_menu = await self.session.execute(stmt_menu)
            menu_item = res_menu.scalar_one_or_none()

            if not menu_item or not menu_item.is_available:
                issues.append(
                    CheckoutIssue(
                        code="ITEM_UNAVAILABLE",
                        message=f"Menu item '{cart_item.menu_item_id}' is unavailable.",
                    )
                )
                unit_price = 0.0
                item_name = "Unavailable Item"
                is_avail = False
            else:
                unit_price = float(menu_item.base_price)
                item_name = menu_item.name
                is_avail = True

                # Check inventory stock
                inv = await self.checkout_repo.get_inventory_item(
                    branch_uuid, cart_item.menu_item_id
                )
                if inv and (not inv.is_in_stock or inv.quantity < cart_item.quantity):
                    is_avail = False
                    issues.append(
                        CheckoutIssue(
                            code="INSUFFICIENT_STOCK",
                            message=f"Item '{menu_item.name}' has insufficient stock (available: {inv.quantity}, requested: {cart_item.quantity}).",
                        )
                    )

            line_subtotal = round(unit_price * cart_item.quantity, 2)
            subtotal += line_subtotal

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
        discount_amount = 0.0
        if req.coupon_code:
            try:
                c_req = CouponCodeValidateRequest(
                    code=req.coupon_code,
                    order_amount=subtotal,
                    branch_id=branch_uuid,
                )
                coupon_val = await self.coupon_service.validate_coupon(
                    user_id=user_uuid,
                    req=c_req,
                )
                discount_amount = min(coupon_val.discount_amount, subtotal)
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    CheckoutIssue(
                        code="INVALID_COUPON",
                        message=getattr(
                            exc, "message", "Coupon code is invalid or expired."
                        ),
                    )
                )

        # 7. Financial Calculations (Tax, Delivery Fee, Final Payable)
        tax_amount = round(subtotal * 0.05, 2)  # 5% GST tax
        delivery_fee = 30.00  # Flat standard delivery fee
        final_payable = round(
            max(0.0, subtotal + tax_amount + delivery_fee - discount_amount), 2
        )

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
