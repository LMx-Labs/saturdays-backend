import uuid
import time
import os

def generate_uuidv7() -> uuid.UUID:
    """Generate a UUIDv7 (time-ordered 128-bit UUID)."""
    if hasattr(uuid, "uuid7"):
        return uuid.uuid7()
    
    # Fallback UUIDv7 generator
    timestamp_ms = int(time.time() * 1000)
    rand_a = int.from_bytes(os.urandom(2), byteorder="big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), byteorder="big") & 0x3FFFFFFFFFFFFFFF
    
    uuid_int = (timestamp_ms & 0xFFFFFFFFFFFF) << 80
    uuid_int |= (0x7 << 76)  # Version 7
    uuid_int |= rand_a << 64
    uuid_int |= (0x2 << 62)  # Variant 10xx
    uuid_int |= rand_b
    
    return uuid.UUID(int=uuid_int)
