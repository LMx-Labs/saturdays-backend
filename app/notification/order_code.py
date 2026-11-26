"""The short code a customer and a restaurant both see for an order ("4821").

This must give exactly the same code as `orderCode()` in the frontend's shared package, so the
WhatsApp message, the student's phone and the restaurant's screen all agree. Built from the random
END of the order id (the start is the same for every order placed in the same minute) as a 4-digit number.
"""

import re


def order_code(order_id: object) -> str:
    hex_digits = re.sub(r"[^0-9a-fA-F]", "", str(order_id or ""))
    if len(hex_digits) < 4:
        return "----"
    n = int(hex_digits[-8:], 16) % 10000
    return f"{n:04d}"
