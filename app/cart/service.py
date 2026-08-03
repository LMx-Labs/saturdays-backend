import uuid
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.cart.models import Cart, CartItem
from app.cart.repository import CartRepositoryInterface
from app.cart.schemas import (
    CartItemAddRequest,
    CartItemResponse,
    CartItemUpdateRequest,
    CartResponse,
    CartValidationIssue,
    CartValidationResponse,
)
from app.core.exceptions import (
    ConflictError,
    EntityNotFoundError,
    UnprocessableEntityError,
)
from app.customer.repository import CustomerRepositoryInterface


class CartServiceInterface(ABC):
    @abstractmethod
    async def get_cart(self, user_id: uuid.UUID) -> CartResponse:
        pass

    @abstractmethod
    async def add_item(
        self, user_id: uuid.UUID, req: CartItemAddRequest
    ) -> CartResponse:
        pass

    @abstractmethod
    async def update_item_quantity(
        self, user_id: uuid.UUID, item_id: uuid.UUID, req: CartItemUpdateRequest
    ) -> CartResponse:
        pass

    @abstractmethod
    async def remove_item(self, user_id: uuid.UUID, item_id: uuid.UUID) -> CartResponse:
        pass

    @abstractmethod
    async def clear_cart(self, user_id: uuid.UUID) -> None:
        pass

    @abstractmethod
    async def validate_cart(self, user_id: uuid.UUID) -> CartValidationResponse:
        pass

    @abstractmethod
    async def purge_expired_carts(self, max_age_days: int = 7) -> int:
        pass


class CartService(CartServiceInterface):
    def __init__(
        self,
        session: AsyncSession,
        cart_repo: CartRepositoryInterface,
        customer_repo: CustomerRepositoryInterface,
    ):
        self.session = session
        self.cart_repo = cart_repo
        self.customer_repo = customer_repo

    async def _get_customer_profile_id(self, user_id: uuid.UUID) -> uuid.UUID:
        profile = await self.customer_repo.get_by_user_id(user_id)
        if not profile:
            raise EntityNotFoundError(
                message="Customer profile not found. Please complete profile registration.",
                error_code="CUSTOMER_NOT_FOUND",
            )
        return profile.id

    def _build_cart_response(self, cart: Cart) -> CartResponse:
        items_resp: list[CartItemResponse] = []
        total_items = 0
        subtotal = 0.0

        for item in cart.items:
            unit_price = float(item.menu_item.base_price) if item.menu_item else 0.0
            item_subtotal = round(unit_price * item.quantity, 2)
            is_avail = item.menu_item.is_available if item.menu_item else False

            total_items += item.quantity
            subtotal += item_subtotal

            items_resp.append(
                CartItemResponse(
                    id=item.id,
                    cart_id=item.cart_id,
                    menu_item_id=item.menu_item_id,
                    quantity=item.quantity,
                    selected_modifiers=item.selected_modifiers,
                    menu_item_name=(
                        item.menu_item.name if item.menu_item else "Unknown Item"
                    ),
                    unit_price=unit_price,
                    subtotal=item_subtotal,
                    is_available=is_avail,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )

        return CartResponse(
            id=cart.id,
            customer_profile_id=cart.customer_profile_id,
            branch_id=cart.branch_id,
            items=items_resp,
            total_items=total_items,
            subtotal=round(subtotal, 2),
            is_expired=cart.is_expired,
            created_at=cart.created_at,
            updated_at=cart.updated_at,
        )

    async def get_cart(self, user_id: uuid.UUID) -> CartResponse:
        profile_id = await self._get_customer_profile_id(user_id)
        cart = await self.cart_repo.get_by_customer_id(profile_id)

        if not cart:
            raise EntityNotFoundError(
                message="Cart is empty.", error_code="CART_NOT_FOUND"
            )

        # Check cart expiry (7-day policy)
        if cart.is_expired:
            await self.cart_repo.clear_cart(cart.id)
            await self.session.commit()
            raise UnprocessableEntityError(
                message="Cart session expired due to inactivity.",
                error_code="CART_EXPIRED",
            )

        return self._build_cart_response(cart)

    async def add_item(
        self, user_id: uuid.UUID, req: CartItemAddRequest
    ) -> CartResponse:
        profile_id = await self._get_customer_profile_id(user_id)

        # 1. Availability check: verify menu_item exists and is available
        menu_item = await self.cart_repo.get_menu_item(req.menu_item_id)
        if not menu_item:
            raise EntityNotFoundError(
                message="Menu item not found.", error_code="MENU_ITEM_NOT_FOUND"
            )

        if not menu_item.is_available:
            raise UnprocessableEntityError(
                message=f"Menu item '{menu_item.name}' is currently unavailable.",
                error_code="ITEM_UNAVAILABLE",
            )

        # 2. INV-CART-002: Positive quantity check
        if req.quantity <= 0:
            raise UnprocessableEntityError(
                message="Quantity must be greater than 0.",
                error_code="INVALID_QUANTITY",
            )

        cart = await self.cart_repo.get_by_customer_id(profile_id)

        # 3. Expiry check on existing cart
        if cart and cart.is_expired:
            await self.cart_repo.delete_cart(cart.id)
            cart = None

        if not cart:
            cart = Cart(
                customer_profile_id=profile_id,
                branch_id=req.branch_id,
            )
            cart = await self.cart_repo.create_cart(cart)
        else:
            # 4. INV-CART-001: Single Branch Constraint
            if cart.branch_id != req.branch_id and len(cart.items) > 0:
                raise ConflictError(
                    message=(
                        "Cart contains items from a different branch. "
                        "Clear your cart before adding items from another store."
                    ),
                    error_code="CROSS_BRANCH_CART_CONFLICT",
                )
            elif cart.branch_id != req.branch_id and len(cart.items) == 0:
                # Update branch_id if cart is empty
                cart.branch_id = req.branch_id

        # 5. Check if item already exists in cart
        existing_item = await self.cart_repo.get_item(cart.id, req.menu_item_id)
        if existing_item:
            new_qty = existing_item.quantity + req.quantity
            await self.cart_repo.update_item(
                existing_item,
                {"quantity": new_qty, "selected_modifiers": req.selected_modifiers},
            )
        else:
            new_item = CartItem(
                cart_id=cart.id,
                menu_item_id=req.menu_item_id,
                quantity=req.quantity,
                selected_modifiers=req.selected_modifiers,
            )
            await self.cart_repo.add_item(new_item)

        cart_id = cart.id
        await self.session.commit()
        self.session.expire_all()
        # Reload full cart with menu items
        updated_cart = await self.cart_repo.get_by_id(cart_id)
        assert updated_cart is not None
        return self._build_cart_response(updated_cart)

    async def update_item_quantity(
        self, user_id: uuid.UUID, item_id: uuid.UUID, req: CartItemUpdateRequest
    ) -> CartResponse:
        profile_id = await self._get_customer_profile_id(user_id)
        cart = await self.cart_repo.get_by_customer_id(profile_id)

        if not cart:
            raise EntityNotFoundError(
                message="Cart not found.", error_code="CART_NOT_FOUND"
            )

        item = await self.cart_repo.get_item_by_id(item_id)
        if not item or item.cart_id != cart.id:
            raise EntityNotFoundError(
                message="Cart item not found.", error_code="CART_ITEM_NOT_FOUND"
            )

        # INV-CART-002: If quantity is 0, delete item
        if req.quantity <= 0:
            await self.cart_repo.delete_item(item.id)
        else:
            await self.cart_repo.update_item(
                item,
                {
                    "quantity": req.quantity,
                    "selected_modifiers": req.selected_modifiers
                    or item.selected_modifiers,
                },
            )

        cart_id = cart.id
        await self.session.commit()
        updated_cart = await self.cart_repo.get_by_id(cart_id)
        assert updated_cart is not None
        return self._build_cart_response(updated_cart)

    async def remove_item(self, user_id: uuid.UUID, item_id: uuid.UUID) -> CartResponse:
        profile_id = await self._get_customer_profile_id(user_id)
        cart = await self.cart_repo.get_by_customer_id(profile_id)

        if not cart:
            raise EntityNotFoundError(
                message="Cart not found.", error_code="CART_NOT_FOUND"
            )

        item = await self.cart_repo.get_item_by_id(item_id)
        if not item or item.cart_id != cart.id:
            raise EntityNotFoundError(
                message="Cart item not found.", error_code="CART_ITEM_NOT_FOUND"
            )

        cart_id = cart.id
        await self.cart_repo.delete_item(item_id)
        await self.session.commit()

        updated_cart = await self.cart_repo.get_by_id(cart_id)
        assert updated_cart is not None
        return self._build_cart_response(updated_cart)

    async def clear_cart(self, user_id: uuid.UUID) -> None:
        profile_id = await self._get_customer_profile_id(user_id)
        cart = await self.cart_repo.get_by_customer_id(profile_id)
        if cart:
            await self.cart_repo.clear_cart(cart.id)
            await self.session.commit()

    async def validate_cart(self, user_id: uuid.UUID) -> CartValidationResponse:
        profile_id = await self._get_customer_profile_id(user_id)
        cart = await self.cart_repo.get_by_customer_id(profile_id)

        if not cart:
            return CartValidationResponse(
                is_valid=False,
                issues=[
                    CartValidationIssue(code="CART_EMPTY", message="Cart is empty.")
                ],
                subtotal=0.0,
                total_items=0,
            )

        issues: list[CartValidationIssue] = []

        if cart.is_expired:
            issues.append(
                CartValidationIssue(
                    code="CART_EXPIRED",
                    message="Cart session has expired due to inactivity (>7 days).",
                )
            )

        subtotal = 0.0
        total_items = 0

        for item in cart.items:
            total_items += item.quantity
            if not item.menu_item or item.menu_item.deleted_at is not None:
                issues.append(
                    CartValidationIssue(
                        code="ITEM_NOT_FOUND",
                        message="Item is no longer available on the menu.",
                        item_id=item.id,
                        menu_item_id=item.menu_item_id,
                    )
                )
            elif not item.menu_item.is_available:
                issues.append(
                    CartValidationIssue(
                        code="ITEM_UNAVAILABLE",
                        message=f"Item '{item.menu_item.name}' is currently out of stock.",
                        item_id=item.id,
                        menu_item_id=item.menu_item_id,
                    )
                )
            else:
                subtotal += float(item.menu_item.base_price) * item.quantity

        is_valid = len(issues) == 0 and total_items > 0

        return CartValidationResponse(
            is_valid=is_valid,
            issues=issues,
            subtotal=round(subtotal, 2),
            total_items=total_items,
        )

    async def purge_expired_carts(self, max_age_days: int = 7) -> int:
        count = await self.cart_repo.delete_expired_carts(max_age_days=max_age_days)
        await self.session.commit()
        return count
