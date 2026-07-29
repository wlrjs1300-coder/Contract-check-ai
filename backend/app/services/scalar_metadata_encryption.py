from __future__ import annotations

from collections.abc import Callable

from backend.app.core.crypto import (
    EncryptionEnvelope,
    build_canonical_aad,
    decrypt,
    encrypt,
)
from backend.app.core.encryption_config import EncryptionKeyring
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    ScalarEncryptionError,
)


SCALAR_METADATA_SCHEMA_VERSION = "scalar-metadata-v1"


def _identifier(
    value: object,
    field_name: str,
    *,
    error_type: type[Exception],
) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or "\x00" in value
    ):
        raise error_type(f"Invalid {field_name} value.")
    return value


def _aad(
    *,
    resource_type: str,
    record_id: str,
    owner_id: str,
    field_name: str,
    error_type: type[Exception],
) -> bytes:
    record_id = _identifier(record_id, "record_id", error_type=error_type)
    owner_id = _identifier(owner_id, "owner_id", error_type=error_type)
    return build_canonical_aad(
        resource_type=resource_type,
        record_id=record_id,
        owner_id=owner_id,
        field_name=field_name,
        schema_version=SCALAR_METADATA_SCHEMA_VERSION,
    )


def _encrypt_required(
    plaintext: str,
    *,
    aad: bytes,
    keyring: EncryptionKeyring,
) -> str:
    if type(plaintext) is not str or plaintext == "":
        raise ScalarEncryptionError("Invalid plaintext.")
    try:
        EncryptionEnvelope.from_json(plaintext)
    except Exception:
        pass
    else:
        raise ScalarEncryptionError("Unable to encrypt value.")
    try:
        return encrypt(
            plaintext.encode("utf-8"),
            aad=aad,
            keyring=keyring,
        ).to_json()
    except Exception:
        raise ScalarEncryptionError("Unable to encrypt value.") from None


def _encrypt_optional(
    plaintext: str | None,
    *,
    aad: bytes,
    keyring: EncryptionKeyring,
) -> str | None:
    if plaintext is None:
        return None
    if type(plaintext) is not str:
        raise ScalarEncryptionError("Invalid plaintext.")
    try:
        EncryptionEnvelope.from_json(plaintext)
    except Exception:
        pass
    else:
        raise ScalarEncryptionError("Unable to encrypt value.")
    try:
        return encrypt(
            plaintext.encode("utf-8"),
            aad=aad,
            keyring=keyring,
        ).to_json()
    except Exception:
        raise ScalarEncryptionError("Unable to encrypt value.") from None


def _decrypt_required(
    encrypted_value: str,
    *,
    aad: bytes,
    keyring: EncryptionKeyring,
) -> str:
    if type(encrypted_value) is not str:
        raise ScalarDecryptionError("Invalid encrypted value.")
    try:
        envelope = EncryptionEnvelope.from_json(encrypted_value)
        return decrypt(envelope, aad=aad, keyring=keyring).decode("utf-8")
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt value.") from None


def _decrypt_optional(
    encrypted_value: str | None,
    *,
    aad: bytes,
    keyring: EncryptionKeyring,
) -> str | None:
    if encrypted_value is None:
        return None
    return _decrypt_required(encrypted_value, aad=aad, keyring=keyring)


def _required_helpers(
    resource_type: str,
    field_name: str,
) -> tuple[Callable[..., str], Callable[..., str]]:
    def encrypt_value(
        plaintext: str,
        *,
        record_id: str,
        owner_id: str,
        keyring: EncryptionKeyring,
    ) -> str:
        return _encrypt_required(
            plaintext,
            aad=_aad(
                resource_type=resource_type,
                record_id=record_id,
                owner_id=owner_id,
                field_name=field_name,
                error_type=ScalarEncryptionError,
            ),
            keyring=keyring,
        )

    def decrypt_value(
        encrypted_value: str,
        *,
        record_id: str,
        owner_id: str,
        keyring: EncryptionKeyring,
    ) -> str:
        return _decrypt_required(
            encrypted_value,
            aad=_aad(
                resource_type=resource_type,
                record_id=record_id,
                owner_id=owner_id,
                field_name=field_name,
                error_type=ScalarDecryptionError,
            ),
            keyring=keyring,
        )

    return encrypt_value, decrypt_value


encrypt_document_filename, decrypt_document_filename = _required_helpers(
    "document", "filename"
)
encrypt_extraction_filename_display, decrypt_extraction_filename_display = (
    _required_helpers("extraction", "filename_display")
)


def encrypt_user_email(
    plaintext: str,
    *,
    user_id: str,
    keyring: EncryptionKeyring,
) -> str:
    encrypt_value, _ = _required_helpers("user", "email")
    return encrypt_value(
        plaintext,
        record_id=user_id,
        owner_id=user_id,
        keyring=keyring,
    )


def decrypt_user_email(
    encrypted_value: str,
    *,
    user_id: str,
    keyring: EncryptionKeyring,
) -> str:
    _, decrypt_value = _required_helpers("user", "email")
    return decrypt_value(
        encrypted_value,
        record_id=user_id,
        owner_id=user_id,
        keyring=keyring,
    )


def encrypt_clause_title(
    plaintext: str | None,
    *,
    clause_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str | None:
    return _encrypt_optional(
        plaintext,
        aad=_aad(
            resource_type="clause",
            record_id=clause_id,
            owner_id=owner_id,
            field_name="title",
            error_type=ScalarEncryptionError,
        ),
        keyring=keyring,
    )


def decrypt_clause_title(
    encrypted_value: str | None,
    *,
    clause_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str | None:
    return _decrypt_optional(
        encrypted_value,
        aad=_aad(
            resource_type="clause",
            record_id=clause_id,
            owner_id=owner_id,
            field_name="title",
            error_type=ScalarDecryptionError,
        ),
        keyring=keyring,
    )
