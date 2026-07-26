from __future__ import annotations

import math

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
    _require_identifier,
)


ANALYSIS_EVIDENCE_SCHEMA_VERSION = "analysis-evidence-v1"
MAX_EVIDENCE_SOURCE_TEXT_LENGTH = 1200

_REQUIRED_METADATA_KEYS = frozenset(
    {
        "evidence_id",
        "document_id",
        "extraction_id",
        "page_number",
        "clause_id",
        "start_offset",
        "end_offset",
        "block_ids",
        "evidence_type",
        "validation_status",
        "confidence",
    }
)
_OPTIONAL_METADATA_KEYS = frozenset(
    {
        "evidence_snapshot_hash",
        "clause_start_offset",
        "clause_end_offset",
    }
)
_PLAINTEXT_KEYS = _REQUIRED_METADATA_KEYS | _OPTIONAL_METADATA_KEYS | {"source_text"}
_ENCRYPTED_KEYS = (
    _REQUIRED_METADATA_KEYS | _OPTIONAL_METADATA_KEYS | {"source_text_encrypted"}
)


def _error(error_type: type[ValueError], detail: str) -> ValueError:
    return error_type(detail)


def _require_item_id(
    value: object,
    field_name: str,
    *,
    error_type: type[ValueError],
) -> str:
    try:
        identifier = _require_identifier(value, field_name, error_type=error_type)
    except TypeError:
        raise _error(error_type, f"Invalid {field_name}.") from None
    if identifier.strip() != identifier or "\x00" in identifier:
        raise _error(error_type, f"Invalid {field_name}.")
    return identifier


def _validate_keys(
    item: object,
    *,
    encrypted: bool,
    error_type: type[ValueError],
) -> dict[str, object]:
    if type(item) is not dict:
        raise _error(error_type, "Invalid evidence item.")
    keys = set(item.keys())
    allowed = _ENCRYPTED_KEYS if encrypted else _PLAINTEXT_KEYS
    required = _REQUIRED_METADATA_KEYS | (
        {"source_text_encrypted"} if encrypted else {"source_text"}
    )
    if not required <= keys or not keys <= allowed:
        raise _error(error_type, "Invalid evidence item.")
    if ("clause_start_offset" in keys) != ("clause_end_offset" in keys):
        raise _error(error_type, "Invalid evidence offsets.")
    return item


def _validate_metadata(
    item: dict[str, object],
    *,
    error_type: type[ValueError],
) -> str:
    evidence_id = _require_item_id(
        item.get("evidence_id"), "evidence_id", error_type=error_type
    )
    for field_name in ("document_id", "extraction_id", "clause_id"):
        _require_item_id(item.get(field_name), field_name, error_type=error_type)

    page_number = item.get("page_number")
    if type(page_number) is not int or page_number < 1:
        raise _error(error_type, "Invalid evidence page number.")

    _require_item_id(
        item.get("evidence_type"), "evidence_type", error_type=error_type
    )
    validation_status = _require_item_id(
        item.get("validation_status"), "validation_status", error_type=error_type
    )

    start_offset = item.get("start_offset")
    end_offset = item.get("end_offset")
    if type(start_offset) is not int or type(end_offset) is not int:
        raise _error(error_type, "Invalid evidence offsets.")
    if validation_status == "not_available":
        if (start_offset, end_offset) != (0, 0):
            raise _error(error_type, "Invalid evidence offsets.")
    elif start_offset < 0 or end_offset <= start_offset:
        raise _error(error_type, "Invalid evidence offsets.")

    if "clause_start_offset" in item:
        clause_start = item.get("clause_start_offset")
        clause_end = item.get("clause_end_offset")
        if (
            type(clause_start) is not int
            or type(clause_end) is not int
            or clause_start < 0
            or clause_end < clause_start
        ):
            raise _error(error_type, "Invalid clause offsets.")

    block_ids = item.get("block_ids")
    if type(block_ids) is not list:
        raise _error(error_type, "Invalid block_ids.")
    seen_block_ids: set[str] = set()
    for block_id in block_ids:
        normalized = _require_item_id(
            block_id, "block_id", error_type=error_type
        )
        if normalized in seen_block_ids:
            raise _error(error_type, "Duplicate block_id value.")
        seen_block_ids.add(normalized)
    if validation_status != "not_available" and not block_ids:
        raise _error(error_type, "Invalid block_ids.")

    confidence = item.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(float(confidence))
        or not 0.0 <= float(confidence) <= 1.0
    ):
        raise _error(error_type, "Invalid evidence confidence.")

    if "evidence_snapshot_hash" in item:
        _require_item_id(
            item.get("evidence_snapshot_hash"),
            "evidence_snapshot_hash",
            error_type=error_type,
        )
    return evidence_id


def _source_text_aad(
    *,
    analysis_job_id: str,
    clause_record_id: str,
    evidence_id: str,
    owner_id: str,
) -> bytes:
    return build_canonical_aad(
        resource_type="analysis_result_evidence",
        record_id=build_canonical_record_id(
            {
                "analysis_job_id": analysis_job_id,
                "clause_record_id": clause_record_id,
                "evidence_id": evidence_id,
            }
        ),
        field_name="source_text",
        owner_id=owner_id,
        schema_version=ANALYSIS_EVIDENCE_SCHEMA_VERSION,
    )


def _validate_context(
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    error_type: type[ValueError],
) -> tuple[str, str, str]:
    return (
        _require_item_id(
            analysis_job_id, "analysis_job_id", error_type=error_type
        ),
        _require_item_id(
            clause_record_id, "clause_record_id", error_type=error_type
        ),
        _require_item_id(owner_id, "owner_id", error_type=error_type),
    )


def encrypt_analysis_evidence_list(
    evidence_list: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(evidence_list) is not list:
        raise ScalarEncryptionError("Invalid evidence list.")
    analysis_job_id, clause_record_id, owner_id = _validate_context(
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        error_type=ScalarEncryptionError,
    )
    encrypted: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for raw_item in evidence_list:
        item = _validate_keys(
            raw_item, encrypted=False, error_type=ScalarEncryptionError
        )
        evidence_id = _validate_metadata(item, error_type=ScalarEncryptionError)
        if evidence_id in seen_ids:
            raise ScalarEncryptionError("Duplicate evidence_id value.")
        seen_ids.add(evidence_id)
        source_text = item.get("source_text")
        if (
            type(source_text) is not str
            or not source_text.strip()
            or len(source_text) > MAX_EVIDENCE_SOURCE_TEXT_LENGTH
        ):
            raise ScalarEncryptionError("Invalid evidence source text.")
        result = dict(item)
        result.pop("source_text")
        try:
            result["source_text_encrypted"] = encrypt(
                source_text.encode("utf-8"),
                aad=_source_text_aad(
                    analysis_job_id=analysis_job_id,
                    clause_record_id=clause_record_id,
                    evidence_id=evidence_id,
                    owner_id=owner_id,
                ),
                keyring=keyring,
            ).to_mapping()
        except Exception:
            raise ScalarEncryptionError("Unable to encrypt evidence.") from None
        encrypted.append(result)
    return encrypted


def decrypt_analysis_evidence_list(
    evidence_list: list[dict[str, object]],
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> list[dict[str, object]]:
    if type(evidence_list) is not list:
        raise ScalarDecryptionError("Invalid evidence list.")
    analysis_job_id, clause_record_id, owner_id = _validate_context(
        analysis_job_id=analysis_job_id,
        clause_record_id=clause_record_id,
        owner_id=owner_id,
        error_type=ScalarDecryptionError,
    )
    decrypted: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for raw_item in evidence_list:
        item = _validate_keys(
            raw_item, encrypted=True, error_type=ScalarDecryptionError
        )
        evidence_id = _validate_metadata(item, error_type=ScalarDecryptionError)
        if evidence_id in seen_ids:
            raise ScalarDecryptionError("Duplicate evidence_id value.")
        seen_ids.add(evidence_id)
        try:
            source_text = decrypt(
                item.get("source_text_encrypted"),
                aad=_source_text_aad(
                    analysis_job_id=analysis_job_id,
                    clause_record_id=clause_record_id,
                    evidence_id=evidence_id,
                    owner_id=owner_id,
                ),
                keyring=keyring,
            ).decode("utf-8")
        except Exception:
            raise ScalarDecryptionError("Unable to decrypt evidence.") from None
        if not source_text.strip() or len(source_text) > MAX_EVIDENCE_SOURCE_TEXT_LENGTH:
            raise ScalarDecryptionError("Invalid evidence source text.")
        result = dict(item)
        result.pop("source_text_encrypted")
        result["source_text"] = source_text
        _validate_keys(result, encrypted=False, error_type=ScalarDecryptionError)
        _validate_metadata(result, error_type=ScalarDecryptionError)
        decrypted.append(result)
    return decrypted
