"""Supported production item pricing for quotes and saved orders.

Tax, delivery fees and discounts are intentionally absent until real policies
and matching payment/receipt behavior are configured.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def money(value: Decimal | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PriceLine:
    unit_price: Decimal
    quantity: int


@dataclass(frozen=True)
class PriceBreakdown:
    subtotal: Decimal
    tax: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total: Decimal

    def snapshot(self) -> dict[str, str]:
        return {
            "subtotal": str(self.subtotal),
            "tax": str(self.tax),
            "delivery_fee": str(self.delivery_fee),
            "discount": str(self.discount),
            "total": str(self.total),
            "currency": "INR",
        }


def calculate_price(lines: list[PriceLine]) -> PriceBreakdown:
    subtotal = sum(
        (money(line.unit_price) * line.quantity for line in lines), Decimal("0.00")
    )
    subtotal = money(subtotal)
    zero = Decimal("0.00")
    return PriceBreakdown(subtotal, zero, zero, zero, subtotal)
