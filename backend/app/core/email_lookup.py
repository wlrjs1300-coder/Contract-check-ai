from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass, field

class EmailLookupConfigurationError(RuntimeError):
    """Raised when the email lookup key is unavailable or invalid."""


@dataclass(frozen=True)
class EmailLookupKey:
    key: bytes = field(repr=False)


def _safe_error() -> str:
    return "Invalid email lookup configuration."


def get_email_lookup_key() -> EmailLookupKey:
    encoded_key = os.getenv("EMAIL_LOOKUP_HMAC_KEY")
    if not encoded_key or encoded_key.strip() != encoded_key:
        raise EmailLookupConfigurationError(_safe_error())
    try:
        key = base64.b64decode(encoded_key, validate=True)
    except Exception:
        raise EmailLookupConfigurationError(_safe_error()) from None
    if len(key) < 32:
        raise EmailLookupConfigurationError(_safe_error())
    return EmailLookupKey(key=key)


def build_email_lookup_hash(
    email: str,
    *,
    lookup_key: EmailLookupKey | None = None,
) -> str:
    if type(email) is not str:
        raise ValueError("Invalid email value.")
    normalized = email.strip().casefold()
    if not normalized:
        raise ValueError("Invalid email value.")
    key = lookup_key or get_email_lookup_key()
    return hmac.new(
        key.key,
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def compare_email_lookup_hash(candidate: str, expected: str) -> bool:
    if type(candidate) is not str or type(expected) is not str:
        return False
    return hmac.compare_digest(candidate, expected)
