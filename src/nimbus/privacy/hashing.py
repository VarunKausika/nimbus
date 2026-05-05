import hashlib
import hmac
import os
from pathlib import Path

SALT_PATH = Path.home() / ".nimbus" / "salt"
HASH_LENGTH = 16  # hex chars (8 bytes)


def load_or_create_salt() -> bytes:
    if SALT_PATH.exists():
        return SALT_PATH.read_bytes()
    salt = os.urandom(32)
    SALT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SALT_PATH.write_bytes(salt)
    return salt


def hash_mac(mac: str, salt: bytes) -> str:
    """Return a truncated HMAC-SHA256 of the MAC address."""
    normalized = mac.lower().replace("-", ":").strip()
    digest = hmac.new(salt, normalized.encode(), hashlib.sha256).hexdigest()
    return digest[:HASH_LENGTH]
