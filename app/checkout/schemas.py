from pydantic import BaseModel, ConfigDict, Field


class CheckoutValidateRequest(BaseModel):
    """Payload for validating a pre-order checkout session."""

    cart_id: str = Field(..., description="UUID of customer active cart")
    coupon_code: str | None = Field(None, description="Optional coupon code applied")
    delivery_address_id: str | None = Field(
        None, description="Optional customer delivery address ID"
    )


class CheckoutItemSummary(BaseModel):
    """Breakdown of individual item line in checkout."""

    model_config = ConfigDict(from_attributes=True)

    menu_item_id: str
    name: str
    unit_price: float
    quantity: int
    subtotal: float
    is_available: bool = True


class CheckoutIssue(BaseModel):
    """Issue or error preventing successful checkout."""

    code: str = Field(..., description="Error classification code")
    message: str = Field(..., description="Human readable explanation")


class CheckoutValidationResponse(BaseModel):
    """Comprehensive checkout summary and validation result."""

    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="True if order can be placed")
    customer_id: str
    branch_id: str
    branch_name: str
    kitchen_id: str | None = None
    cart_id: str
    subtotal: float
    tax_amount: float
    delivery_fee: float
    discount_amount: float
    final_payable_amount: float
    coupon_code: str | None = None
    items: list[CheckoutItemSummary]
    issues: list[CheckoutIssue] = []
