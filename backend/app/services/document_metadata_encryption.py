from __future__ import annotations

from backend.app.core.crypto import (
    build_canonical_aad,
    build_canonical_record_id,
    decrypt,
    encrypt,
)
from backend.app.core.encryption_config import EncryptionKeyring
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    ScalarEncryptionError,
)


DOCUMENT_METADATA_SCHEMA_VERSION = "document-metadata-v1"
_ENCRYPTED_ITEM_KEYS = frozenset({"item_index", "text_encrypted"})


def _require_identifier(
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


def _item_aad(document_id: str, owner_id: str, item_index: int) -> bytes:
    return build_canonical_aad(
        resource_type="document_unclassified_section",
        record_id=build_canonical_record_id(
            {"document_id": document_id, "item_index": item_index}
        ),
        field_name="text",
        owner_id=owner_id,
        schema_version=DOCUMENT_METADATA_SCHEMA_VERSION,
    )


def encrypt_unclassified_sections(
    sections: list[str],
    *,
    document_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    document_id = _require_identifier(
        document_id, "document_id", error_type=ScalarEncryptionError
    )
    owner_id = _require_identifier(
        owner_id, "owner_id", error_type=ScalarEncryptionError
    )
    if type(sections) is not list:
        raise ScalarEncryptionError("Invalid unclassified_sections value.")

    encrypted_sections: list[dict[str, object]] = []
    for item_index, section in enumerate(sections):
        if type(section) is not str:
            raise ScalarEncryptionError("Invalid unclassified section entry.")
        try:
            envelope = encrypt(
                section.encode("utf-8"),
                aad=_item_aad(document_id, owner_id, item_index),
                keyring=keyring,
            )
        except Exception:
            raise ScalarEncryptionError(
                "Unable to encrypt unclassified section."
            ) from None
        encrypted_sections.append(
            {
                "item_index": item_index,
                "text_encrypted": envelope.to_mapping(),
            }
        )
    return encrypted_sections


def decrypt_unclassified_sections(
    sections: list[dict[str, object]],
    *,
    document_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[str]:
    document_id = _require_identifier(
        document_id, "document_id", error_type=ScalarDecryptionError
    )
    owner_id = _require_identifier(
        owner_id, "owner_id", error_type=ScalarDecryptionError
    )
    if type(sections) is not list:
        raise ScalarDecryptionError("Invalid unclassified_sections value.")

    plaintext_sections: list[str] = []
    for expected_index, item in enumerate(sections):
        if type(item) is not dict or set(item.keys()) != _ENCRYPTED_ITEM_KEYS:
            raise ScalarDecryptionError("Invalid unclassified section entry.")
        if type(item.get("item_index")) is not int:
            raise ScalarDecryptionError("Invalid unclassified section entry.")
        if item["item_index"] != expected_index:
            raise ScalarDecryptionError("Invalid unclassified section order.")
        try:
            plaintext = decrypt(
                item.get("text_encrypted"),
                aad=_item_aad(document_id, owner_id, expected_index),
                keyring=keyring,
            ).decode("utf-8")
        except Exception:
            raise ScalarDecryptionError(
                "Unable to decrypt unclassified section."
            ) from None
        plaintext_sections.append(plaintext)
    return plaintext_sections
