from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from typing import Mapping


class EncryptionConfigurationError(RuntimeError):
    """Raised when encryption configuration is invalid."""


class EncryptionError(RuntimeError):
    """Base exception for encryption runtime failures."""


class EnvelopeValidationError(EncryptionError):
    """Raised when an encryption envelope is malformed."""


class EncryptionFailedError(EncryptionError):
    """Raised when encryption operation fails."""


class DecryptionFailedError(EncryptionError):
    """Raised when decryption operation fails."""


class AadValidationError(EncryptionError):
    """Raised when AAD construction inputs are invalid."""


class KeyLookupError(EncryptionError):
    """Raised when a requested encryption key is unavailable."""


@dataclass(frozen=True)
class EncryptionKey:
    key_id: str
    key: bytes = field(repr=False, compare=True)
    status: str


@dataclass(frozen=True)
class EncryptionKeyring:
    _keys: tuple[EncryptionKey, ...]
    _active_key_id: str

    def __post_init__(self) -> None:
        if not self._keys:
            raise EncryptionConfigurationError("Invalid encryption configuration.")
        object.__setattr__(
            self,
            "active_key",
            self._require_key(
                self._active_key_id,
                allow_decrypt_only=False,
                runtime=False,
            ),
        )
        object.__setattr__(
            self,
            "decrypt_only_keys",
            tuple(k for k in self._keys if k.status == "decrypt_only"),
        )

    def _require_key(
        self,
        key_id: str,
        *,
        allow_decrypt_only: bool,
        runtime: bool,
    ) -> EncryptionKey:
        for key in self._keys:
            if key.key_id == key_id:
                if key.status == "active":
                    return key
                if key.status == "decrypt_only" and allow_decrypt_only:
                    return key
                if runtime:
                    raise KeyLookupError("Unable to use encryption key.")
                raise EncryptionConfigurationError("Invalid encryption key state.")
        if runtime:
            raise KeyLookupError("Unable to use encryption key.")
        raise EncryptionConfigurationError("Unknown encryption key.")

    def get_active_key(self) -> EncryptionKey:
        return self._require_key(
            self._active_key_id,
            allow_decrypt_only=False,
            runtime=True,
        )

    def get_key(self, key_id: str) -> EncryptionKey:
        return self._require_key(
            key_id,
            allow_decrypt_only=True,
            runtime=True,
        )


_KEY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _build_message_safe_error() -> str:
    return "Invalid encryption configuration."


def _decode_key_value(raw_key: str) -> bytes:
    try:
        decoded = base64.b64decode(raw_key, validate=True)
    except Exception:
        raise EncryptionConfigurationError(_build_message_safe_error()) from None
    if len(decoded) != 32:
        raise EncryptionConfigurationError(_build_message_safe_error())
    return decoded


def _validate_key_id(value: object) -> str:
    if type(value) is not str:
        raise EncryptionConfigurationError(_build_message_safe_error())
    if not _KEY_ID_PATTERN.fullmatch(value):
        raise EncryptionConfigurationError(_build_message_safe_error())
    return value


def _validate_key_status(value: object) -> str:
    if type(value) is not str:
        raise EncryptionConfigurationError(_build_message_safe_error())
    if value not in {"active", "decrypt_only"}:
        raise EncryptionConfigurationError(_build_message_safe_error())
    return value


def _validate_key_item(item: Mapping[str, object]) -> tuple[str, bytes, str]:
    if set(item.keys()) != {"key_id", "key", "status"}:
        raise EncryptionConfigurationError(_build_message_safe_error())

    key_id = _validate_key_id(item["key_id"])
    status = _validate_key_status(item["status"])
    key_value = item["key"]
    if type(key_value) is not str:
        raise EncryptionConfigurationError(_build_message_safe_error())

    decoded_key = _decode_key_value(key_value)
    return key_id, decoded_key, status


def get_encryption_keyring() -> EncryptionKeyring:
    keys_json = os.getenv("DATA_ENCRYPTION_KEYS_JSON")
    active_key_id = os.getenv("DATA_ENCRYPTION_ACTIVE_KEY_ID")

    if keys_json is None or active_key_id is None or not keys_json or not active_key_id:
        raise EncryptionConfigurationError(_build_message_safe_error())

    try:
        raw_keys = json.loads(keys_json)
    except Exception:
        raise EncryptionConfigurationError(_build_message_safe_error()) from None

    if type(raw_keys) is not list or len(raw_keys) == 0:
        raise EncryptionConfigurationError(_build_message_safe_error())

    parsed_keys: list[EncryptionKey] = []
    key_ids: set[str] = set()
    active_count = 0

    for item in raw_keys:
        if type(item) is not dict:
            raise EncryptionConfigurationError(_build_message_safe_error())
        mapping = dict(item)
        key_id, key_value, status = _validate_key_item(mapping)

        if key_id in key_ids:
            raise EncryptionConfigurationError(_build_message_safe_error())
        key_ids.add(key_id)

        if status == "active":
            active_count += 1

        if "\x00" in key_id or key_id.strip() != key_id:
            raise EncryptionConfigurationError(_build_message_safe_error())

        if not key_id:
            raise EncryptionConfigurationError(_build_message_safe_error())

        # key_value already decoded and validated; avoid storing string raw representation.
        parsed_keys.append(EncryptionKey(key_id=key_id, key=key_value, status=status))

    if active_count != 1:
        raise EncryptionConfigurationError(_build_message_safe_error())
    if active_key_id not in key_ids:
        raise EncryptionConfigurationError(_build_message_safe_error())
    active_key_id_checked = _validate_key_id(active_key_id)
    if active_key_id != active_key_id_checked:
        raise EncryptionConfigurationError(_build_message_safe_error())

    active_key_is_active = False
    for key in parsed_keys:
        if key.key_id == active_key_id_checked and key.status == "active":
            active_key_is_active = True
            break
    if not active_key_is_active:
        raise EncryptionConfigurationError(_build_message_safe_error())

    return EncryptionKeyring(_keys=tuple(parsed_keys), _active_key_id=active_key_id_checked)
