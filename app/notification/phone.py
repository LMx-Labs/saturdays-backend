"""Turning the mobile numbers people type into the form WhatsApp needs."""

import re

# Indian mobile numbers start with 6, 7, 8 or 9 and have ten digits.
_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def normalize_phone(raw: str | None, default_country_code: str = "91") -> str | None:
    """Return the number as digits with its country code ("919876543210"), or None.

    Accepts the ways people actually write a number: "98765 43210", "098765-43210",
    "+91 98765 43210", "0091 98765 43210", "(91) 98765 43210". A bare ten-digit number
    is taken to be Indian. Anything that cannot be a mobile number gives None, so a
    typo is caught when it is entered, not when a message silently fails to arrive.
    """
    if not raw:
        return None
    text = raw.strip()
    international = text.startswith(("+", "00"))
    digits = re.sub(r"\D", "", text)
    if text.startswith("00"):
        digits = digits[2:]
    if not digits:
        return None

    cc = re.sub(r"\D", "", default_country_code) or "91"

    if international:
        if digits.startswith(cc):
            local = digits[len(cc) :]
            if cc == "91" and not _INDIAN_MOBILE.match(local):
                return None
        return digits if 11 <= len(digits) <= 15 and digits[0] != "0" else None

    if cc == "91":
        if _INDIAN_MOBILE.match(digits):  # 9876543210
            return cc + digits
        if (
            len(digits) == 11
            and digits.startswith("0")
            and _INDIAN_MOBILE.match(digits[1:])
        ):
            return cc + digits[1:]  # 09876543210
        if (
            len(digits) == 12
            and digits.startswith("91")
            and _INDIAN_MOBILE.match(digits[2:])
        ):
            return digits  # 919876543210
        return None

    # Any other home country: accept a full international number typed without the plus.
    return digits if 11 <= len(digits) <= 15 and digits[0] != "0" else None


def mask_phone(digits: str | None) -> str:
    """ "919876543210" -> "+91 ••••• ••210": enough to recognise, safe to put in a log."""
    if not digits:
        return "(none)"
    return f"+{digits[:2]} {'•' * max(len(digits) - 5, 0)}{digits[-3:]}"
