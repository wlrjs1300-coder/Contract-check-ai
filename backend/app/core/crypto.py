from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
import base64
import json
import os
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.app.core.encryption_config import (
    AadValidationError,
    DecryptionFailedError,
    EnvelopeValidationError,
    EncryptionFailedError,
    EncryptionKeyring,
    KeyLookupError,
)


def _safe_error() -> str:
    return "Invalid encryption envelope."


@dataclass(frozen=True)
class EncryptionEnvelope:
    enc_version: int
    key_id: str
    algorithm: str
    nonce: str = field(repr=False)
    ciphertext: str = field(repr=False)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "EncryptionEnvelope":
        if type(value) is not dict:
            raise EnvelopeValidationError(_safe_error())
        if set(value.keys()) != {"enc_version", "key_id", "algorithm", "nonce", "ciphertext"}:
            raise EnvelopeValidationError(_safe_error())

        return cls(
            enc_version=value["enc_version"],  # type: ignore[arg-type]
            key_id=value["key_id"],  # type: ignore[arg-type]
            algorithm=value["algorithm"],  # type: ignore[arg-type]
            nonce=value["nonce"],  # type: ignore[arg-type]
            ciphertext=value["ciphertext"],  # type: ignore[arg-type]
        )

    def __post_init__(self) -> None:
        if type(self.enc_version) is not int or self.enc_version != 1:
            raise EnvelopeValidationError(_safe_error())
        if type(self.key_id) is not str:
            raise EnvelopeValidationError(_safe_error())
        if not _KEY_ID_PATTERN.fullmatch(self.key_id):
            raise EnvelopeValidationError(_safe_error())
        if type(self.algorithm) is not str or self.algorithm != "AES-256-GCM":
            raise EnvelopeValidationError(_safe_error())
        if type(self.nonce) is not str or type(self.ciphertext) is not str:
            raise EnvelopeValidationError(_safe_error())

        if len(_decode_strict_b64(self.nonce)) != 12:
            raise EnvelopeValidationError(_safe_error())
        if len(_decode_strict_b64(self.ciphertext)) < 16:
            raise EnvelopeValidationError(_safe_error())

    def decode(self) -> tuple[bytes, bytes, str]:
        return (
            _decode_strict_b64(self.nonce),
            _decode_strict_b64(self.ciphertext),
            self.algorithm,
        )


def _decode_strict_b64(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except Exception:
        raise EnvelopeValidationError(_safe_error()) from None


def _encode_b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def build_canonical_aad(
    *,
    resource_type: str,
    record_id: str,
    field_name: str,
    owner_id: str,
    schema_version: str,
) -> bytes:
    for key_value in (
        resource_type,
        record_id,
        field_name,
        owner_id,
        schema_version,
    ):
        if type(key_value) is not str:
            raise AadValidationError("Invalid AAD value.")
        if key_value == "" or key_value.strip() != key_value or "\x00" in key_value:
            raise AadValidationError("Invalid AAD value.")

    payload = {
        "resource_type": resource_type,
        "record_id": record_id,
        "field_name": field_name,
        "owner_id": owner_id,
        "schema_version": schema_version,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def encrypt(
    plaintext: bytes,
    *,
    aad: bytes,
    keyring: EncryptionKeyring,
) -> EncryptionEnvelope:
    if type(plaintext) is not bytes:
        raise EncryptionFailedError("Unable to encrypt value.")
    if type(aad) is not bytes:
        raise EncryptionFailedError("Unable to encrypt value.")
    key = keyring.get_active_key()
    nonce = os.urandom(12)
    try:
        ciphertext = AESGCM(key.key).encrypt(nonce, plaintext, aad)
    except Exception:
        raise EncryptionFailedError("Unable to encrypt value.") from None

    return EncryptionEnvelope(
        enc_version=1,
        key_id=key.key_id,
        algorithm="AES-256-GCM",
        nonce=_encode_b64(nonce),
        ciphertext=_encode_b64(ciphertext),
    )


def _parse_envelope(
    envelope: EncryptionEnvelope | Mapping[str, object],
) -> EncryptionEnvelope:
    if isinstance(envelope, EncryptionEnvelope):
        return envelope
    return EncryptionEnvelope.from_mapping(envelope)


def decrypt(
    envelope: EncryptionEnvelope | Mapping[str, object],
    *,
    aad: bytes,
    keyring: EncryptionKeyring,
) -> bytes:
    if type(aad) is not bytes:
        raise DecryptionFailedError("Unable to decrypt value.")
    envelope_obj = _parse_envelope(envelope)
    if envelope_obj.algorithm != "AES-256-GCM":
        raise EnvelopeValidationError("Invalid encryption envelope.")
    if not envelope_obj.key_id:
        raise DecryptionFailedError("Unable to decrypt value.")

    nonce, ciphertext, _ = envelope_obj.decode()
    if len(ciphertext) < 16:
        raise DecryptionFailedError("Unable to decrypt value.")
    try:
        key = keyring.get_key(envelope_obj.key_id)
    except KeyLookupError:
        raise DecryptionFailedError("Unable to decrypt value.") from None
    except Exception:
        raise DecryptionFailedError("Unable to decrypt value.") from None
    try:
        return AESGCM(key.key).decrypt(nonce, ciphertext, aad)
    except Exception:
        raise DecryptionFailedError("Unable to decrypt value.") from None


_KEY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
