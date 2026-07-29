from __future__ import annotations

from collections.abc import Callable

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
    _ensure_utf8_plaintext,
    _ensure_utf8_text,
    _require_identifier,
)


NESTED_JSON_SCHEMA_VERSION = "nested-json-v1"

_PAGE_TEXT_FIELD_NAMES = frozenset({"reviewed_text", "final_text"})
_BLOCK_PLAINTEXT_KEYS = frozenset({"block_index", "text", "confidence", "bbox", "reading_order"})
_BLOCK_ENCRYPTED_KEYS = frozenset({"block_index", "text_encrypted", "confidence", "bbox", "reading_order"})
_SNAPSHOT_PAGE_PLAINTEXT_KEYS = frozenset(
    {"page_id", "page_number", "final_text", "text_source", "text_changed", "method", "warnings", "blocks"}
)
_SNAPSHOT_PAGE_ENCRYPTED_KEYS = frozenset(
    {
        "page_id",
        "page_number",
        "final_text_encrypted",
        "text_source",
        "text_changed",
        "method",
        "warnings",
        "blocks",
    }
)


def _require_page_number(value: object, *, error_type: type[Exception]) -> int:
    if type(value) is not int or value < 1:
        raise error_type("Invalid page_number value.")
    return value


def _require_block_index(value: object, *, error_type: type[Exception]) -> int:
    if type(value) is not int or value < 0:
        raise error_type("Invalid block_index value.")
    return value


def _require_snapshot_version(value: object, *, error_type: type[Exception]) -> int:
    if type(value) is not int or value < 1:
        raise error_type("Invalid snapshot_version value.")
    return value


def _block_aad(*, extraction_id: str, page_number: int, block_index: int, owner_id: str) -> bytes:
    return build_canonical_aad(
        resource_type="extraction_page_block",
        record_id=build_canonical_record_id(
            {
                "extraction_id": extraction_id,
                "page_number": page_number,
                "block_index": block_index,
            }
        ),
        field_name="text",
        owner_id=owner_id,
        schema_version=NESTED_JSON_SCHEMA_VERSION,
    )


def _snapshot_block_aad(
    *,
    extraction_id: str,
    snapshot_version: int,
    page_number: int,
    block_index: int,
    owner_id: str,
) -> bytes:
    """AAD domain for confirmation_snapshot block text.

    Deliberately distinct resource_type/record_id from `_block_aad` so a block
    ciphertext copied between ExtractionPage.extra_data.blocks and
    Extraction.extra_data.confirmation_snapshot[*].blocks (same extraction_id,
    page_number, block_index) fails to decrypt in the other context.
    """
    return build_canonical_aad(
        resource_type="confirmation_snapshot_block",
        record_id=build_canonical_record_id(
            {
                "extraction_id": extraction_id,
                "snapshot_version": snapshot_version,
                "page_number": page_number,
                "block_index": block_index,
            }
        ),
        field_name="text",
        owner_id=owner_id,
        schema_version=NESTED_JSON_SCHEMA_VERSION,
    )


def _page_text_field_aad(*, extraction_id: str, page_number: int, field_name: str, owner_id: str) -> bytes:
    return build_canonical_aad(
        resource_type="extraction_page_extra",
        record_id=build_canonical_record_id(
            {
                "extraction_id": extraction_id,
                "page_number": page_number,
            }
        ),
        field_name=field_name,
        owner_id=owner_id,
        schema_version=NESTED_JSON_SCHEMA_VERSION,
    )


def _snapshot_final_text_aad(
    *,
    extraction_id: str,
    page_number: int,
    snapshot_version: int,
    owner_id: str,
) -> bytes:
    return build_canonical_aad(
        resource_type="confirmation_snapshot_page",
        record_id=build_canonical_record_id(
            {
                "extraction_id": extraction_id,
                "page_number": page_number,
                "snapshot_version": snapshot_version,
            }
        ),
        field_name="final_text",
        owner_id=owner_id,
        schema_version=NESTED_JSON_SCHEMA_VERSION,
    )


def _encrypt_block_list(
    blocks: list[dict[str, object]],
    *,
    keyring: EncryptionKeyring,
    aad_for_block: Callable[[int], bytes],
) -> list[dict[str, object]]:
    if type(blocks) is not list:
        raise ScalarEncryptionError("Invalid blocks value.")

    seen_indexes: set[int] = set()
    encrypted_blocks: list[dict[str, object]] = []
    for block in blocks:
        if type(block) is not dict or set(block.keys()) != _BLOCK_PLAINTEXT_KEYS:
            raise ScalarEncryptionError("Invalid block entry.")

        block_index = _require_block_index(block.get("block_index"), error_type=ScalarEncryptionError)
        if block_index in seen_indexes:
            raise ScalarEncryptionError("Duplicate block_index value.")
        seen_indexes.add(block_index)

        text = block.get("text")
        if type(text) is not str:
            raise ScalarEncryptionError("Invalid block text value.")

        envelope = encrypt(
            _ensure_utf8_text(text),
            aad=aad_for_block(block_index),
            keyring=keyring,
        )
        encrypted_blocks.append(
            {
                "block_index": block_index,
                "text_encrypted": envelope.to_mapping(),
                "confidence": block.get("confidence"),
                "bbox": block.get("bbox"),
                "reading_order": block.get("reading_order"),
            }
        )
    return encrypted_blocks


def _decrypt_block_list(
    blocks: list[dict[str, object]],
    *,
    keyring: EncryptionKeyring,
    aad_for_block: Callable[[int], bytes],
) -> list[dict[str, object]]:
    if type(blocks) is not list:
        raise ScalarDecryptionError("Invalid blocks value.")

    seen_indexes: set[int] = set()
    decrypted_blocks: list[dict[str, object]] = []
    for block in blocks:
        if type(block) is not dict or set(block.keys()) != _BLOCK_ENCRYPTED_KEYS:
            raise ScalarDecryptionError("Invalid block entry.")

        block_index = _require_block_index(block.get("block_index"), error_type=ScalarDecryptionError)
        if block_index in seen_indexes:
            raise ScalarDecryptionError("Duplicate block_index value.")
        seen_indexes.add(block_index)

        envelope_value = block.get("text_encrypted")
        if type(envelope_value) is not dict:
            raise ScalarDecryptionError("Invalid block text_encrypted value.")

        try:
            plaintext = decrypt(
                envelope_value,
                aad=aad_for_block(block_index),
                keyring=keyring,
            )
        except Exception:
            raise ScalarDecryptionError("Unable to decrypt block text.") from None

        decrypted_blocks.append(
            {
                "block_index": block_index,
                "text": _ensure_utf8_plaintext(plaintext),
                "confidence": block.get("confidence"),
                "bbox": block.get("bbox"),
                "reading_order": block.get("reading_order"),
            }
        )
    return decrypted_blocks


def encrypt_extraction_page_blocks(
    blocks: list[dict[str, object]],
    *,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarEncryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)
    page_number = _require_page_number(page_number, error_type=ScalarEncryptionError)
    return _encrypt_block_list(
        blocks,
        keyring=keyring,
        aad_for_block=lambda block_index: _block_aad(
            extraction_id=extraction_id,
            page_number=page_number,
            block_index=block_index,
            owner_id=owner_id,
        ),
    )


def decrypt_extraction_page_blocks(
    blocks: list[dict[str, object]],
    *,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarDecryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)
    page_number = _require_page_number(page_number, error_type=ScalarDecryptionError)
    return _decrypt_block_list(
        blocks,
        keyring=keyring,
        aad_for_block=lambda block_index: _block_aad(
            extraction_id=extraction_id,
            page_number=page_number,
            block_index=block_index,
            owner_id=owner_id,
        ),
    )


def encrypt_confirmation_snapshot_blocks(
    blocks: list[dict[str, object]],
    *,
    extraction_id: str,
    snapshot_version: int,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    """Encrypt block text for confirmation_snapshot storage using a distinct
    AAD domain from `encrypt_extraction_page_blocks`, so ciphertext cannot be
    swapped between the two storage contexts even when extraction_id,
    page_number and block_index all coincide."""
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarEncryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)
    page_number = _require_page_number(page_number, error_type=ScalarEncryptionError)
    snapshot_version = _require_snapshot_version(snapshot_version, error_type=ScalarEncryptionError)
    return _encrypt_block_list(
        blocks,
        keyring=keyring,
        aad_for_block=lambda block_index: _snapshot_block_aad(
            extraction_id=extraction_id,
            snapshot_version=snapshot_version,
            page_number=page_number,
            block_index=block_index,
            owner_id=owner_id,
        ),
    )


def decrypt_confirmation_snapshot_blocks(
    blocks: list[dict[str, object]],
    *,
    extraction_id: str,
    snapshot_version: int,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarDecryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)
    page_number = _require_page_number(page_number, error_type=ScalarDecryptionError)
    snapshot_version = _require_snapshot_version(snapshot_version, error_type=ScalarDecryptionError)
    return _decrypt_block_list(
        blocks,
        keyring=keyring,
        aad_for_block=lambda block_index: _snapshot_block_aad(
            extraction_id=extraction_id,
            snapshot_version=snapshot_version,
            page_number=page_number,
            block_index=block_index,
            owner_id=owner_id,
        ),
    )


def encrypt_extraction_page_text_field(
    value: str | None,
    *,
    field_name: str,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> dict[str, object] | None:
    if field_name not in _PAGE_TEXT_FIELD_NAMES:
        raise ScalarEncryptionError("Invalid field_name value.")
    if value is None:
        return None
    if type(value) is not str:
        raise ScalarEncryptionError(f"Invalid {field_name} value.")

    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarEncryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)
    page_number = _require_page_number(page_number, error_type=ScalarEncryptionError)

    envelope = encrypt(
        _ensure_utf8_text(value),
        aad=_page_text_field_aad(
            extraction_id=extraction_id,
            page_number=page_number,
            field_name=field_name,
            owner_id=owner_id,
        ),
        keyring=keyring,
    )
    return envelope.to_mapping()


def decrypt_extraction_page_text_field(
    envelope_value: dict[str, object] | None,
    *,
    field_name: str,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str | None:
    if field_name not in _PAGE_TEXT_FIELD_NAMES:
        raise ScalarDecryptionError("Invalid field_name value.")
    if envelope_value is None:
        return None
    if type(envelope_value) is not dict:
        raise ScalarDecryptionError(f"Invalid {field_name}_encrypted value.")

    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarDecryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)
    page_number = _require_page_number(page_number, error_type=ScalarDecryptionError)

    try:
        plaintext = decrypt(
            envelope_value,
            aad=_page_text_field_aad(
                extraction_id=extraction_id,
                page_number=page_number,
                field_name=field_name,
                owner_id=owner_id,
            ),
            keyring=keyring,
        )
    except Exception:
        raise ScalarDecryptionError(f"Unable to decrypt {field_name}.") from None
    return _ensure_utf8_plaintext(plaintext)


def write_extraction_page_text_field(
    page_data: dict[str, object],
    *,
    field_name: str,
    value: str | None,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> dict[str, object]:
    """Return a copy of page_data with `{field_name}_encrypted` set and the legacy
    plaintext key removed, so plaintext and ciphertext can never coexist."""
    if field_name not in _PAGE_TEXT_FIELD_NAMES:
        raise ScalarEncryptionError("Invalid field_name value.")
    if type(page_data) is not dict:
        raise ScalarEncryptionError("Invalid page extra_data value.")

    updated = dict(page_data)
    updated.pop(field_name, None)
    updated[f"{field_name}_encrypted"] = encrypt_extraction_page_text_field(
        value,
        field_name=field_name,
        extraction_id=extraction_id,
        page_number=page_number,
        owner_id=owner_id,
        keyring=keyring,
    )
    return updated


def read_extraction_page_text_field(
    page_data: dict[str, object],
    *,
    field_name: str,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str | None:
    """Fail-closed read: any surviving plaintext value under the legacy key name
    (whether from a pre-migration row or a dual-write bug) is rejected rather than
    silently returned."""
    if field_name not in _PAGE_TEXT_FIELD_NAMES:
        raise ScalarDecryptionError("Invalid field_name value.")
    if type(page_data) is not dict:
        raise ScalarDecryptionError("Invalid page extra_data value.")

    if page_data.get(field_name) is not None:
        raise ScalarDecryptionError(
            f"Legacy or conflicting plaintext {field_name} value is not supported."
        )

    encrypted_key = f"{field_name}_encrypted"
    if encrypted_key not in page_data:
        return None

    return decrypt_extraction_page_text_field(
        page_data.get(encrypted_key),
        field_name=field_name,
        extraction_id=extraction_id,
        page_number=page_number,
        owner_id=owner_id,
        keyring=keyring,
    )


def encrypt_confirmation_snapshot(
    snapshot: list[dict[str, object]],
    *,
    extraction_id: str,
    owner_id: str,
    snapshot_version: int,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarEncryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)
    snapshot_version = _require_snapshot_version(snapshot_version, error_type=ScalarEncryptionError)
    if type(snapshot) is not list:
        raise ScalarEncryptionError("Invalid confirmation snapshot value.")

    encrypted_pages: list[dict[str, object]] = []
    seen_page_numbers: set[int] = set()
    for page in snapshot:
        if type(page) is not dict or set(page.keys()) != _SNAPSHOT_PAGE_PLAINTEXT_KEYS:
            raise ScalarEncryptionError("Invalid confirmation snapshot page.")

        page_number = _require_page_number(page.get("page_number"), error_type=ScalarEncryptionError)
        if page_number in seen_page_numbers:
            raise ScalarEncryptionError("Duplicate page_number value.")
        seen_page_numbers.add(page_number)

        final_text = page.get("final_text")
        if type(final_text) is not str:
            raise ScalarEncryptionError("Invalid final_text value.")

        blocks = page.get("blocks")
        encrypted_blocks = encrypt_confirmation_snapshot_blocks(
            blocks if isinstance(blocks, list) else [],
            extraction_id=extraction_id,
            snapshot_version=snapshot_version,
            page_number=page_number,
            owner_id=owner_id,
            keyring=keyring,
        )

        final_text_envelope = encrypt(
            _ensure_utf8_text(final_text),
            aad=_snapshot_final_text_aad(
                extraction_id=extraction_id,
                page_number=page_number,
                snapshot_version=snapshot_version,
                owner_id=owner_id,
            ),
            keyring=keyring,
        )

        encrypted_pages.append(
            {
                "page_id": page.get("page_id"),
                "page_number": page_number,
                "final_text_encrypted": final_text_envelope.to_mapping(),
                "text_source": page.get("text_source"),
                "text_changed": page.get("text_changed"),
                "method": page.get("method"),
                "warnings": page.get("warnings"),
                "blocks": encrypted_blocks,
            }
        )
    return encrypted_pages


def decrypt_confirmation_snapshot(
    stored_snapshot: list[dict[str, object]],
    *,
    extraction_id: str,
    owner_id: str,
    snapshot_version: int | None,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarDecryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)
    snapshot_version = _require_snapshot_version(snapshot_version, error_type=ScalarDecryptionError)
    if type(stored_snapshot) is not list:
        raise ScalarDecryptionError("Invalid confirmation snapshot value.")

    decrypted_pages: list[dict[str, object]] = []
    seen_page_numbers: set[int] = set()
    for page in stored_snapshot:
        if type(page) is not dict or set(page.keys()) != _SNAPSHOT_PAGE_ENCRYPTED_KEYS:
            raise ScalarDecryptionError("Invalid confirmation snapshot page.")

        page_number = _require_page_number(page.get("page_number"), error_type=ScalarDecryptionError)
        if page_number in seen_page_numbers:
            raise ScalarDecryptionError("Duplicate page_number value.")
        seen_page_numbers.add(page_number)

        final_text_envelope = page.get("final_text_encrypted")
        if type(final_text_envelope) is not dict:
            raise ScalarDecryptionError("Invalid final_text_encrypted value.")

        try:
            plaintext = decrypt(
                final_text_envelope,
                aad=_snapshot_final_text_aad(
                    extraction_id=extraction_id,
                    page_number=page_number,
                    snapshot_version=snapshot_version,
                    owner_id=owner_id,
                ),
                keyring=keyring,
            )
        except Exception:
            raise ScalarDecryptionError("Unable to decrypt confirmation snapshot final_text.") from None

        blocks = page.get("blocks")
        decrypted_blocks = decrypt_confirmation_snapshot_blocks(
            blocks if isinstance(blocks, list) else [],
            extraction_id=extraction_id,
            snapshot_version=snapshot_version,
            page_number=page_number,
            owner_id=owner_id,
            keyring=keyring,
        )

        decrypted_pages.append(
            {
                "page_id": page.get("page_id"),
                "page_number": page_number,
                "final_text": _ensure_utf8_plaintext(plaintext),
                "text_source": page.get("text_source"),
                "text_changed": page.get("text_changed"),
                "method": page.get("method"),
                "warnings": page.get("warnings"),
                "blocks": decrypted_blocks,
            }
        )
    return decrypted_pages
