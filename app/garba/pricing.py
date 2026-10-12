"""Server-side prices and limits for Saturdays Garba Night. Never trust the client."""

from datetime import timedelta

EVENT_NAME = "Saturdays Garba Night"
VENUE = "The Hooks"
STARTS_AT = "15:00"
ENDS_AT = "20:00"
EVENT_DATES = {"17": "2026-10-17", "18": "2026-10-18"}
HOLD_FOR = timedelta(minutes=15)

CATEGORIES = ("men", "women", "couple")
DATE_CHOICES = ("17", "18", "both")

CAPACITY = {"men": 35, "women": 55, "couple": 30}
MAX_PER_BOOKING = {"men": 4, "women": 4, "couple": 2}

# Rupees. One-day passes share a price; "both" is a single pass, not two day passes.
_ONE_DAY = {"men": 499, "women": 499, "couple": 799}
_BOTH_DAYS = {"men": 799, "women": 799, "couple": 1399}

TICKET_PREFIX = {"men": "GN26-MN", "women": "GN26-WN", "couple": "GN26-CP"}


def unit_price(category: str, dates: str) -> int:
    table = _BOTH_DAYS if dates == "both" else _ONE_DAY
    try:
        return table[category]
    except KeyError as exc:
        raise ValueError(f"Unknown category '{category}'") from exc


def total_amount(category: str, dates: str, quantity: int) -> int:
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")
    return unit_price(category, dates) * quantity


def attendee_count(category: str, quantity: int) -> int:
    """A couple pass is two people. Quantity 1 couple means 2 attendees."""
    if category == "couple":
        return quantity * 2
    return quantity


def prices_for(category: str) -> dict[str, int]:
    one = unit_price(category, "17")
    return {"17": one, "18": one, "both": unit_price(category, "both")}
