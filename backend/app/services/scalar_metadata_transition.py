from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from backend.app.services.scalar_encryption import ScalarDecryptionError


T = TypeVar("T")
TransitionState = Literal[
    "encrypted_only",
    "matching_dual",
    "legacy_plaintext",
    "missing",
]


@dataclass(frozen=True)
class TransitionScalar(Generic[T]):
    value: T | None
    state: TransitionState


def resolve_transition_scalar(
    plaintext: T | None,
    decrypted_encrypted: T | None,
    *,
    encrypted_present: bool,
    allow_missing: bool,
) -> TransitionScalar[T]:
    if encrypted_present:
        if decrypted_encrypted is None and not allow_missing:
            raise ScalarDecryptionError("Stored encrypted data is unavailable.")
        if plaintext is None:
            return TransitionScalar(decrypted_encrypted, "encrypted_only")
        if plaintext != decrypted_encrypted:
            raise ScalarDecryptionError("Stored encrypted data is unavailable.")
        return TransitionScalar(decrypted_encrypted, "matching_dual")
    if plaintext is not None:
        return TransitionScalar(plaintext, "legacy_plaintext")
    if allow_missing:
        return TransitionScalar(None, "missing")
    raise ScalarDecryptionError("Stored encrypted data is unavailable.")
