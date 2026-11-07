"""The short code a customer and a restaurant both see for an order ("K7M2").

This must give exactly the same code as `orderCode()` in the frontend's shared package, so the
WhatsApp message, the student's phone and the restaurant's screen all agree. Built from the random
END of the order id (the start is the same for every order placed in the same minute), using
letters and digits that are hard to confuse when read aloud: no 0, O, 1, I or L.
"""

import re

_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # 31 symbols
_LENGTH = 4
_SPACE = len(_ALPHABET) ** _LENGTH


def order_code(order_id: object) -> str:
    hex_digits = re.sub(r"[^0-9a-fA-F]", "", str(order_id or ""))
    if len(hex_digits) < 4:
        return "----"
    n = int(hex_digits[-8:], 16) % _SPACE
    code = ""
    for _ in range(_LENGTH):
        code = _ALPHABET[n % len(_ALPHABET)] + code
        n //= len(_ALPHABET)
    return code
