from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.core.crypto import build_canonical_aad, encrypt
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.services.analysis_evidence_encryption import (
    decrypt_analysis_evidence_list,
    encrypt_analysis_evidence_list,
)
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    ScalarEncryptionError,
)


def _keyring():
    return get_encryption_keyring()


def _identity(**overrides: str) -> dict[str, str]:
    value = {
        "analysis_job_id": "job-1",
        "clause_record_id": "clause-record-1",
        "owner_id": "owner-1",
    }
    value.update(overrides)
    return value


def _evidence(evidence_id: str = "doc:clause:1-e001") -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "document_id": "doc-1",
        "extraction_id": "doc-1",
        "page_number": 1,
        "clause_id": "doc:clause:1",
        "source_text": "The payment is due within thirty days.",
        "start_offset": 4,
        "end_offset": 42,
        "block_ids": ["p1-b1"],
        "evidence_type": "source_quote",
        "validation_status": "exact_match",
        "confidence": 1.0,
        "evidence_snapshot_hash": "abc123",
        "clause_start_offset": 0,
        "clause_end_offset": 100,
    }


def _not_available() -> dict[str, object]:
    value = _evidence()
    value.update(
        start_offset=0,
        end_offset=0,
        block_ids=[],
        validation_status="not_available",
    )
    value.pop("evidence_snapshot_hash")
    value.pop("clause_start_offset")
    value.pop("clause_end_offset")
    return value


def _encrypt(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return encrypt_analysis_evidence_list(items, keyring=_keyring(), **_identity())


def _decrypt(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return decrypt_analysis_evidence_list(items, keyring=_keyring(), **_identity())


@pytest.mark.parametrize("plaintext", [[_evidence()], [_not_available()]])
def test_evidence_round_trip(plaintext: list[dict[str, object]]) -> None:
    encrypted = _encrypt(plaintext)
    assert "source_text" not in encrypted[0]
    assert "source_text_encrypted" in encrypted[0]
    assert _decrypt(encrypted) == plaintext


def test_same_plaintext_uses_different_nonce_and_ciphertext() -> None:
    first = _encrypt([_evidence()])[0]["source_text_encrypted"]
    second = _encrypt([_evidence()])[0]["source_text_encrypted"]
    assert isinstance(first, dict) and isinstance(second, dict)
    assert first["nonce"] != second["nonce"]
    assert first["ciphertext"] != second["ciphertext"]


@pytest.mark.parametrize("field", ["nonce", "ciphertext"])
def test_evidence_rejects_envelope_tamper(field: str) -> None:
    encrypted = _encrypt([_evidence()])
    envelope = encrypted[0]["source_text_encrypted"]
    assert isinstance(envelope, dict)
    original = str(envelope[field])
    envelope[field] = ("B" if original.startswith("A") else "A") + original[1:]
    with pytest.raises(ScalarDecryptionError):
        _decrypt(encrypted)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("owner_id", "other-owner"),
        ("analysis_job_id", "other-job"),
        ("clause_record_id", "other-clause"),
    ],
)
def test_evidence_rejects_wrong_aad_context(field: str, value: str) -> None:
    encrypted = _encrypt([_evidence()])
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_evidence_list(
            encrypted,
            keyring=_keyring(),
            **_identity(**{field: value}),
        )


def test_evidence_rejects_changed_id_and_item_ciphertext_swap() -> None:
    encrypted = _encrypt(
        [_evidence("doc:clause:1-e001"), _evidence("doc:clause:1-e002")]
    )
    changed = deepcopy(encrypted)
    changed[0]["evidence_id"] = "doc:clause:1-e999"
    with pytest.raises(ScalarDecryptionError):
        _decrypt(changed)
    encrypted[0]["source_text_encrypted"], encrypted[1]["source_text_encrypted"] = (
        encrypted[1]["source_text_encrypted"],
        encrypted[0]["source_text_encrypted"],
    )
    with pytest.raises(ScalarDecryptionError):
        _decrypt(encrypted)


def test_evidence_rejects_other_field_or_schema_ciphertext() -> None:
    encrypted = _encrypt([_evidence()])
    encrypted[0]["source_text_encrypted"] = encrypt(
        b"The payment is due within thirty days.",
        aad=build_canonical_aad(
            resource_type="analysis_result_evidence",
            record_id="other-record",
            field_name="other_field",
            owner_id="owner-1",
            schema_version="other-schema-v1",
        ),
        keyring=_keyring(),
    ).to_mapping()
    with pytest.raises(ScalarDecryptionError):
        _decrypt(encrypted)


def test_evidence_list_order_is_not_part_of_aad() -> None:
    plaintext = [_evidence("doc:clause:1-e001"), _evidence("doc:clause:1-e002")]
    assert _decrypt(list(reversed(_encrypt(plaintext)))) == list(reversed(plaintext))


def test_schema_rejects_dual_write_unknown_missing_and_legacy_plaintext() -> None:
    for mutation in (
        lambda item: item.update(source_text_encrypted={}),
        lambda item: item.update(unknown="value"),
        lambda item: item.pop("document_id"),
    ):
        item = _evidence()
        mutation(item)
        with pytest.raises(ScalarEncryptionError):
            _encrypt([item])
    with pytest.raises(ScalarDecryptionError):
        _decrypt([_evidence()])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_id", ""),
        ("evidence_id", " "),
        ("evidence_id", " e-1"),
        ("evidence_id", "e-1 "),
        ("evidence_id", "e-\x001"),
        ("document_id", 1),
        ("extraction_id", ""),
        ("clause_id", " "),
    ],
)
def test_evidence_rejects_invalid_ids(field: str, value: object) -> None:
    item = _evidence()
    item[field] = value
    with pytest.raises(ScalarEncryptionError):
        _encrypt([item])


def test_evidence_rejects_duplicate_evidence_and_block_ids() -> None:
    with pytest.raises(ScalarEncryptionError, match="Duplicate evidence_id"):
        _encrypt([_evidence(), _evidence()])
    item = _evidence()
    item["block_ids"] = ["p1-b1", "p1-b1"]
    with pytest.raises(ScalarEncryptionError, match="Duplicate block_id"):
        _encrypt([item])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_offset", True),
        ("start_offset", -1),
        ("start_offset", 42),
        ("end_offset", False),
        ("end_offset", 3),
    ],
)
def test_evidence_rejects_invalid_offsets(field: str, value: object) -> None:
    item = _evidence()
    item[field] = value
    with pytest.raises(ScalarEncryptionError):
        _encrypt([item])


def test_only_not_available_allows_zero_offsets() -> None:
    item = _evidence()
    item.update(start_offset=0, end_offset=0)
    with pytest.raises(ScalarEncryptionError):
        _encrypt([item])
    assert _decrypt(_encrypt([_not_available()])) == [_not_available()]


@pytest.mark.parametrize("page_number", [True, 0, -1, 1.5])
def test_evidence_rejects_invalid_page_number(page_number: object) -> None:
    item = _evidence()
    item["page_number"] = page_number
    with pytest.raises(ScalarEncryptionError):
        _encrypt([item])


@pytest.mark.parametrize(
    "confidence",
    [True, -0.1, 1.1, float("nan"), float("inf"), "1.0"],
)
def test_evidence_rejects_invalid_confidence(confidence: object) -> None:
    item = _evidence()
    item["confidence"] = confidence
    with pytest.raises(ScalarEncryptionError):
        _encrypt([item])


def test_error_message_does_not_expose_plaintext() -> None:
    plaintext = _evidence()
    encrypted = _encrypt([plaintext])
    encrypted[0]["evidence_id"] = "changed-id"
    with pytest.raises(ScalarDecryptionError) as excinfo:
        _decrypt(encrypted)
    assert str(plaintext["source_text"]) not in str(excinfo.value)
