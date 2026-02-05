"""PIN hashing and verification utilities (using PBKDF2)."""
import os
import hashlib
import binascii
from typing import Tuple

# PBKDF2 params
_ITER = 100_000
_HASH_NAME = "sha256"
_SALT_BYTES = 16


def make_pin_hash(pin: str) -> Tuple[str, str]:
    """Return (salt_hex, hash_hex)"""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, pin.encode("utf-8"), salt, _ITER)
    return binascii.hexlify(salt).decode("ascii"), binascii.hexlify(dk).decode("ascii")


def verify_pin(pin: str, salt_hex: str, hash_hex: str) -> bool:
    salt = binascii.unhexlify(salt_hex.encode("ascii"))
    expected = binascii.unhexlify(hash_hex.encode("ascii"))
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, pin.encode("utf-8"), salt, _ITER)
    return hashlib.compare_digest(dk, expected)
