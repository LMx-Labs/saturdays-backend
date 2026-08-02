import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """
    Generates a RFC 9562 / UUIDv7 timestamp-ordered 128-bit UUID.
    Timestamp bits: 48-bit unix timestamp in milliseconds.
    Version: 4 bits (0111 = 7).
    Variant: 2 bits (10 = RFC 4122 / 9562).
    Random bits: 62 random bits.
    """
    ts_ms = int(time.time() * 1000)
    rand_bytes = os.urandom(10)

    # 48-bit timestamp
    time_high = (ts_ms >> 16) & 0xFFFFFFFF
    time_low = ts_ms & 0xFFFF

    # 12-bit rand_a with version 7 (0x7000)
    rand_a = (rand_bytes[0] << 8) | rand_bytes[1]
    ver_rand_a = 0x7000 | (rand_a & 0x0FFF)

    # 62-bit rand_b with variant 2 (0x8000)
    rand_b_high = (rand_bytes[2] << 8) | rand_bytes[3]
    var_rand_b = 0x8000 | (rand_b_high & 0x3FFF)

    node = int.from_bytes(rand_bytes[4:], byteorder="big")

    uuid_int = (
        (time_high << 96)
        | (time_low << 80)
        | (ver_rand_a << 64)
        | (var_rand_b << 48)
        | node
    )
    return uuid.UUID(int=uuid_int)


def uuid7_str() -> str:
    return str(uuid7())
