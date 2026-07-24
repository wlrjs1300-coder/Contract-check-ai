from __future__ import annotations

import json

from backend.app.core.crypto import (
    EnvelopeValidationError,
    encrypt,
    decrypt,
    build_canonical_aad,
    EncryptionEnvelope,
)
from backend.app.core.encryption_config import EncryptionKeyring


class ScalarEncryptionError(RuntimeError):
    """Raised when scalar encryption operation is invalid."""


class ScalarDecryptionError(RuntimeError):
    """Raised when scalar decryption operation cannot decode or verify payload."""


def _build_canonical_record_id(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _require_str(value: object, field_name: str, *, error_type: type[Exception]) -> str:
    if type(value) is not str:
        raise error_type(f"Invalid {field_name} value.")
    return value


def _require_identifier(value: object, field_name: str, *, error_type: type[Exception]) -> str:
    if type(value) is not str:
        raise error_type(f"Invalid {field_name} value.")
    if not value:
        raise error_type(f"Invalid {field_name} value.")
    if value.strip() != value:
        raise error_type(f"Invalid {field_name} value.")
    if "\x00" in value:
        raise error_type(f"Invalid {field_name} value.")
    return value


def _require_int(value: object, field_name: str, *, error_type: type[Exception]) -> int:
    if type(value) is not int:
        raise error_type(f"Invalid {field_name} value.")
    return value


def _require_positive_int(value: int, field_name: str, *, error_type: type[Exception]) -> int:
    if value <= 0:
        raise error_type(f"Invalid {field_name} value.")
    return value


def _ensure_utf8_text(value: str) -> bytes:
    try:
        return value.encode("utf-8")
    except Exception:
        raise ScalarEncryptionError("Unable to encode plaintext.") from None


def _ensure_utf8_plaintext(value: bytes) -> str:
    try:
        return value.decode("utf-8")
    except Exception:
        raise ScalarDecryptionError("Unable to decode plaintext.") from None


def _clause_body_aad(clause_id: str, owner_id: str) -> bytes:
    return build_canonical_aad(
        resource_type="clause",
        record_id=clause_id,
        field_name="body",
        owner_id=owner_id,
        schema_version="scalar-v1",
    )


def _reject_double_encryption(plaintext: str) -> None:
    if type(plaintext) is not str:
        return
    if not plaintext.startswith("{") or not plaintext.endswith("}"):
        return
    try:
        EncryptionEnvelope.from_json(plaintext)
    except EnvelopeValidationError:
        return
    except Exception:
        raise
    raise ScalarEncryptionError("Unable to encrypt value.")


def _extraction_page_aad(extraction_id: str, page_number: int, owner_id: str) -> bytes:
    return build_canonical_aad(
        resource_type="extraction_page",
        record_id=_build_canonical_record_id(
            {
                "extraction_id": extraction_id,
                "page_number": page_number,
            },
        ),
        field_name="text",
        owner_id=owner_id,
        schema_version="scalar-v1",
    )


def _analysis_result_summary_aad(
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
) -> bytes:
    return build_canonical_aad(
        resource_type="analysis_result_item",
        record_id=_build_canonical_record_id(
            {
                "analysis_job_id": analysis_job_id,
                "clause_record_id": clause_record_id,
            },
        ),
        field_name="summary",
        owner_id=owner_id,
        schema_version="scalar-v1",
    )


def encrypt_clause_body(
    plaintext: str,
    *,
    clause_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str:
    if type(plaintext) is not str:
        raise ScalarEncryptionError("Invalid plaintext.")
    clause_id = _require_identifier(clause_id, "clause_id", error_type=ScalarEncryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)
    _reject_double_encryption(plaintext)

    try:
        envelope = encrypt(
            _ensure_utf8_text(plaintext),
            aad=_clause_body_aad(clause_id, owner_id),
            keyring=keyring,
        )
        return envelope.to_json()
    except Exception as exc:
        if isinstance(exc, ScalarEncryptionError):
            raise
        raise ScalarEncryptionError("Unable to encrypt clause body.") from None


def decrypt_clause_body(
    encrypted_value: str,
    *,
    clause_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str:
    encrypted_value = _require_str(encrypted_value, "encrypted_value", error_type=ScalarDecryptionError)
    clause_id = _require_identifier(clause_id, "clause_id", error_type=ScalarDecryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)

    try:
        envelope = EncryptionEnvelope.from_json(encrypted_value)
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt clause body.") from None

    try:
        plaintext = decrypt(
            envelope,
            aad=_clause_body_aad(clause_id, owner_id),
            keyring=keyring,
        )
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt clause body.") from None
    return _ensure_utf8_plaintext(plaintext)


def encrypt_extraction_page_text(
    plaintext: str,
    *,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str:
    if type(plaintext) is not str:
        raise ScalarEncryptionError("Invalid plaintext.")
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarEncryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)
    page_number = _require_positive_int(
        _require_int(page_number, "page_number", error_type=ScalarEncryptionError),
        "page_number",
        error_type=ScalarEncryptionError,
    )
    _reject_double_encryption(plaintext)

    try:
        envelope = encrypt(
            _ensure_utf8_text(plaintext),
            aad=_extraction_page_aad(extraction_id, page_number, owner_id),
            keyring=keyring,
        )
        return envelope.to_json()
    except Exception as exc:
        if isinstance(exc, ScalarEncryptionError):
            raise
        raise ScalarEncryptionError("Unable to encrypt extraction page text.") from None


def decrypt_extraction_page_text(
    encrypted_value: str,
    *,
    extraction_id: str,
    page_number: int,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str:
    encrypted_value = _require_str(encrypted_value, "encrypted_value", error_type=ScalarDecryptionError)
    extraction_id = _require_identifier(extraction_id, "extraction_id", error_type=ScalarDecryptionError)
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)
    page_number = _require_positive_int(
        _require_int(page_number, "page_number", error_type=ScalarDecryptionError),
        "page_number",
        error_type=ScalarDecryptionError,
    )

    try:
        envelope = EncryptionEnvelope.from_json(encrypted_value)
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt extraction page text.") from None

    try:
        plaintext = decrypt(
            envelope,
            aad=_extraction_page_aad(extraction_id, page_number, owner_id),
            keyring=keyring,
        )
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt extraction page text.") from None
    return _ensure_utf8_plaintext(plaintext)


def encrypt_analysis_result_summary(
    plaintext: str,
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str:
    if type(plaintext) is not str:
        raise ScalarEncryptionError("Invalid plaintext.")
    analysis_job_id = _require_identifier(
        analysis_job_id, "analysis_job_id", error_type=ScalarEncryptionError
    )
    clause_record_id = _require_identifier(
        clause_record_id, "clause_record_id", error_type=ScalarEncryptionError
    )
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarEncryptionError)
    _reject_double_encryption(plaintext)

    try:
        envelope = encrypt(
            _ensure_utf8_text(plaintext),
            aad=_analysis_result_summary_aad(
                analysis_job_id=analysis_job_id,
                clause_record_id=clause_record_id,
                owner_id=owner_id,
            ),
            keyring=keyring,
        )
        return envelope.to_json()
    except Exception as exc:
        if isinstance(exc, ScalarEncryptionError):
            raise
        raise ScalarEncryptionError("Unable to encrypt analysis result summary.") from None


def decrypt_analysis_result_summary(
    encrypted_value: str,
    *,
    analysis_job_id: str,
    clause_record_id: str,
    owner_id: str,
    keyring: EncryptionKeyring,
) -> str:
    encrypted_value = _require_str(encrypted_value, "encrypted_value", error_type=ScalarDecryptionError)
    analysis_job_id = _require_identifier(
        analysis_job_id, "analysis_job_id", error_type=ScalarDecryptionError
    )
    clause_record_id = _require_identifier(
        clause_record_id, "clause_record_id", error_type=ScalarDecryptionError
    )
    owner_id = _require_identifier(owner_id, "owner_id", error_type=ScalarDecryptionError)

    try:
        envelope = EncryptionEnvelope.from_json(encrypted_value)
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt analysis result summary.") from None

    try:
        plaintext = decrypt(
            envelope,
            aad=_analysis_result_summary_aad(
                analysis_job_id=analysis_job_id,
                clause_record_id=clause_record_id,
                owner_id=owner_id,
            ),
            keyring=keyring,
        )
    except Exception:
        raise ScalarDecryptionError("Unable to decrypt analysis result summary.") from None
    return _ensure_utf8_plaintext(plaintext)
