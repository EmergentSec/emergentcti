"""API key generation and Fernet encryption for feed credentials."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets

from cryptography.fernet import Fernet

from cti.core.config import get_settings


# ── API key generation ───────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        A 3-tuple of ``(raw_key, key_hash, key_prefix)``:

        - **raw_key** — the full key to show the user once, e.g. ``cti_<32-byte-urlsafe>``.
        - **key_hash** — SHA-256 hex digest of *raw_key* (stored in the database).
        - **key_prefix** — first 12 characters of *raw_key* (for display/identification).
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"cti_{random_part}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]
    return raw_key, key_hash, key_prefix


# ── Fernet encryption for feed auth configs ──────────────────────────────

def _get_fernet() -> Fernet:
    """Derive a Fernet instance from the configured encryption key.

    The ``FEED_ENCRYPTION_KEY`` setting is treated as passphrase material:
    we SHA-256 hash it and use the first 32 bytes as a url-safe-base64
    Fernet key.
    """
    settings = get_settings()
    raw = settings.FEED_ENCRYPTION_KEY.get_secret_value().encode()
    digest = hashlib.sha256(raw).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_config(data: dict) -> bytes:
    """Encrypt a dictionary as JSON bytes using Fernet.

    Args:
        data: Arbitrary dict (e.g. ``{"api_key": "abc123"}``).

    Returns:
        Fernet-encrypted ciphertext suitable for storing in a BYTEA column.
    """
    fernet = _get_fernet()
    plaintext = json.dumps(data).encode()
    return fernet.encrypt(plaintext)


def decrypt_config(encrypted: bytes) -> dict:
    """Decrypt Fernet ciphertext back to a dictionary.

    Args:
        encrypted: Ciphertext previously produced by :func:`encrypt_config`.

    Returns:
        The original dictionary.
    """
    fernet = _get_fernet()
    plaintext = fernet.decrypt(encrypted)
    return json.loads(plaintext)
