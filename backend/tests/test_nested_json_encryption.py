from __future__ import annotations

import base64

import pytest

from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.services.scalar_encryption import ScalarDecryptionError, ScalarEncryptionError
from backend.app.services.nested_json_encryption import (
    decrypt_confirmation_snapshot,
    decrypt_confirmation_snapshot_blocks,
    decrypt_extraction_page_blocks,
    decrypt_extraction_page_text_field,
    encrypt_confirmation_snapshot,
    encrypt_confirmation_snapshot_blocks,
    encrypt_extraction_page_blocks,
    encrypt_extraction_page_text_field,
    read_extraction_page_text_field,
    write_extraction_page_text_field,
)


def _keyring():
    return get_encryption_keyring()


OWNER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_OWNER_ID = "22222222-2222-4222-8222-222222222222"


def _sample_block(index: int, text: str) -> dict[str, object]:
    return {
        "block_index": index,
        "text": text,
        "confidence": 0.97,
        "bbox": [0, 0, 10, 10],
        "reading_order": index,
    }


# 1. ExtractionPage reviewed_text round trip
def test_reviewed_text_round_trip() -> None:
    keyring = _keyring()
    envelope = encrypt_extraction_page_text_field(
        "수정된 페이지 본문입니다.",
        field_name="reviewed_text",
        extraction_id="ex-001",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert isinstance(envelope, dict)
    assert set(envelope.keys()) == {"enc_version", "key_id", "algorithm", "nonce", "ciphertext"}
    plaintext = decrypt_extraction_page_text_field(
        envelope,
        field_name="reviewed_text",
        extraction_id="ex-001",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert plaintext == "수정된 페이지 본문입니다."


# 2. ExtractionPage final_text round trip
def test_final_text_round_trip() -> None:
    keyring = _keyring()
    envelope = encrypt_extraction_page_text_field(
        "최종 확정 텍스트입니다.",
        field_name="final_text",
        extraction_id="ex-002",
        page_number=2,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    plaintext = decrypt_extraction_page_text_field(
        envelope,
        field_name="final_text",
        extraction_id="ex-002",
        page_number=2,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert plaintext == "최종 확정 텍스트입니다."


def test_page_text_field_none_round_trips_to_none() -> None:
    keyring = _keyring()
    envelope = encrypt_extraction_page_text_field(
        None,
        field_name="reviewed_text",
        extraction_id="ex-003",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert envelope is None
    assert (
        decrypt_extraction_page_text_field(
            None,
            field_name="reviewed_text",
            extraction_id="ex-003",
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )
        is None
    )


# 3. ExtractionPage blocks[*].text round trip
def test_extraction_page_blocks_round_trip() -> None:
    keyring = _keyring()
    blocks = [_sample_block(0, "첫 번째 블록"), _sample_block(1, "두 번째 블록")]
    encrypted = encrypt_extraction_page_blocks(
        blocks,
        extraction_id="ex-blocks",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert all(set(b.keys()) == {"block_index", "text_encrypted", "confidence", "bbox", "reading_order"} for b in encrypted)
    decrypted = decrypt_extraction_page_blocks(
        encrypted,
        extraction_id="ex-blocks",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert decrypted == blocks


def test_extraction_page_blocks_empty_list_round_trips() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_blocks(
        [], extraction_id="ex-empty", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    assert encrypted == []
    assert (
        decrypt_extraction_page_blocks(
            [], extraction_id="ex-empty", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )
        == []
    )


# 4. confirmation_snapshot final_text round trip + 5. block text round trip
def test_confirmation_snapshot_round_trip() -> None:
    keyring = _keyring()
    plaintext_snapshot = [
        {
            "page_id": "1",
            "page_number": 1,
            "final_text": "확정된 첫 페이지 본문",
            "text_source": "edited",
            "text_changed": True,
            "method": "ocr",
            "warnings": [],
            "blocks": [_sample_block(0, "블록 본문")],
        }
    ]
    encrypted = encrypt_confirmation_snapshot(
        plaintext_snapshot,
        extraction_id="ex-snap",
        owner_id=OWNER_ID,
        snapshot_version=3,
        keyring=keyring,
    )
    assert "final_text_encrypted" in encrypted[0]
    assert "final_text" not in encrypted[0]

    decrypted = decrypt_confirmation_snapshot(
        encrypted,
        extraction_id="ex-snap",
        owner_id=OWNER_ID,
        snapshot_version=3,
        keyring=keyring,
    )
    assert decrypted == plaintext_snapshot


# AAD domain separation between ExtractionPage.extra_data.blocks and
# Extraction.extra_data.confirmation_snapshot[*].blocks (same extraction_id,
# page_number, block_index must NOT be cross-decryptable).
def test_page_block_ciphertext_rejected_in_snapshot_block_context() -> None:
    keyring = _keyring()
    page_encrypted = encrypt_extraction_page_blocks(
        [_sample_block(0, "페이지 블록 본문")],
        extraction_id="ex-cross",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_confirmation_snapshot_blocks(
            page_encrypted,
            extraction_id="ex-cross",
            snapshot_version=1,
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )


def test_page_block_ciphertext_rejected_inside_full_snapshot_decrypt() -> None:
    """End-to-end version of the substitution: splice a page-level block
    ciphertext into a stored confirmation_snapshot at the matching
    extraction_id/page_number/block_index and confirm the whole snapshot
    decrypt fails closed instead of silently succeeding."""
    keyring = _keyring()
    page_encrypted = encrypt_extraction_page_blocks(
        [_sample_block(0, "페이지 블록 본문")],
        extraction_id="ex-cross-2",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )

    plaintext_snapshot = [
        {
            "page_id": "1",
            "page_number": 1,
            "final_text": "스냅샷 본문",
            "text_source": "original",
            "text_changed": False,
            "method": "ocr",
            "warnings": [],
            "blocks": [_sample_block(0, "스냅샷 블록 본문")],
        }
    ]
    encrypted_snapshot = encrypt_confirmation_snapshot(
        plaintext_snapshot,
        extraction_id="ex-cross-2",
        owner_id=OWNER_ID,
        snapshot_version=1,
        keyring=keyring,
    )
    # Splice the page-level ciphertext into the snapshot's block list.
    tampered_snapshot = [dict(encrypted_snapshot[0])]
    tampered_snapshot[0]["blocks"] = page_encrypted

    with pytest.raises(ScalarDecryptionError):
        decrypt_confirmation_snapshot(
            tampered_snapshot,
            extraction_id="ex-cross-2",
            owner_id=OWNER_ID,
            snapshot_version=1,
            keyring=keyring,
        )


def test_snapshot_block_ciphertext_rejected_in_page_block_context() -> None:
    keyring = _keyring()
    snapshot_encrypted = encrypt_confirmation_snapshot_blocks(
        [_sample_block(0, "스냅샷 블록 본문")],
        extraction_id="ex-cross-3",
        snapshot_version=1,
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_blocks(
            snapshot_encrypted,
            extraction_id="ex-cross-3",
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )


def test_snapshot_block_aad_bound_to_snapshot_version() -> None:
    """The snapshot block AAD itself (not just final_text) must be bound to
    snapshot_version, independent of the whole-snapshot decrypt path."""
    keyring = _keyring()
    encrypted = encrypt_confirmation_snapshot_blocks(
        [_sample_block(0, "본문")],
        extraction_id="ex-cross-4",
        snapshot_version=1,
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    # Same snapshot_version decrypts fine.
    decrypted = decrypt_confirmation_snapshot_blocks(
        encrypted,
        extraction_id="ex-cross-4",
        snapshot_version=1,
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert decrypted == [_sample_block(0, "본문")]

    # A different snapshot_version must fail even though extraction_id,
    # page_number, block_index and owner_id are unchanged.
    with pytest.raises(ScalarDecryptionError):
        decrypt_confirmation_snapshot_blocks(
            encrypted,
            extraction_id="ex-cross-4",
            snapshot_version=2,
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )


def test_confirmation_snapshot_blocks_round_trip_independent_of_page_blocks() -> None:
    keyring = _keyring()
    blocks = [_sample_block(0, "첫 번째"), _sample_block(1, "두 번째")]
    encrypted = encrypt_confirmation_snapshot_blocks(
        blocks,
        extraction_id="ex-snap-blocks",
        snapshot_version=5,
        page_number=2,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert all(
        set(b.keys()) == {"block_index", "text_encrypted", "confidence", "bbox", "reading_order"}
        for b in encrypted
    )
    decrypted = decrypt_confirmation_snapshot_blocks(
        encrypted,
        extraction_id="ex-snap-blocks",
        snapshot_version=5,
        page_number=2,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert decrypted == blocks


# 6. Same plaintext encrypted twice produces different ciphertext
def test_same_plaintext_produces_different_ciphertext() -> None:
    keyring = _keyring()
    first = encrypt_extraction_page_text_field(
        "동일한 본문", field_name="final_text", extraction_id="ex-004", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    second = encrypt_extraction_page_text_field(
        "동일한 본문", field_name="final_text", extraction_id="ex-004", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    assert first["ciphertext"] != second["ciphertext"]
    assert first["nonce"] != second["nonce"]


# 7. Envelope tamper failure
def test_tampered_ciphertext_fails() -> None:
    keyring = _keyring()
    envelope = encrypt_extraction_page_text_field(
        "본문", field_name="reviewed_text", extraction_id="ex-005", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    tampered = dict(envelope)
    decoded = bytearray(base64.b64decode(tampered["ciphertext"]))
    decoded[-1] ^= 0xFF
    tampered["ciphertext"] = base64.b64encode(bytes(decoded)).decode("ascii")

    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text_field(
            tampered, field_name="reviewed_text", extraction_id="ex-005", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


# 8. AAD owner_id mismatch failure
def test_owner_id_mismatch_fails() -> None:
    keyring = _keyring()
    envelope = encrypt_extraction_page_text_field(
        "본문", field_name="reviewed_text", extraction_id="ex-006", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text_field(
            envelope,
            field_name="reviewed_text",
            extraction_id="ex-006",
            page_number=1,
            owner_id=OTHER_OWNER_ID,
            keyring=keyring,
        )


# 9. page_number mismatch failure
def test_page_number_mismatch_fails() -> None:
    keyring = _keyring()
    envelope = encrypt_extraction_page_text_field(
        "본문", field_name="final_text", extraction_id="ex-007", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text_field(
            envelope, field_name="final_text", extraction_id="ex-007", page_number=2, owner_id=OWNER_ID, keyring=keyring
        )


def test_extraction_id_mismatch_fails_for_blocks() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_blocks(
        [_sample_block(0, "본문")], extraction_id="ex-008", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_blocks(
            encrypted, extraction_id="ex-008-wrong", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_snapshot_version_mismatch_fails() -> None:
    keyring = _keyring()
    plaintext_snapshot = [
        {
            "page_id": "1",
            "page_number": 1,
            "final_text": "본문",
            "text_source": "original",
            "text_changed": False,
            "method": "direct",
            "warnings": [],
            "blocks": [],
        }
    ]
    encrypted = encrypt_confirmation_snapshot(
        plaintext_snapshot, extraction_id="ex-009", owner_id=OWNER_ID, snapshot_version=1, keyring=keyring
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_confirmation_snapshot(
            encrypted, extraction_id="ex-009", owner_id=OWNER_ID, snapshot_version=2, keyring=keyring
        )


# 10. block_index mismatch/duplicate failure
def test_duplicate_block_index_rejected_on_encrypt() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_extraction_page_blocks(
            [_sample_block(0, "a"), _sample_block(0, "b")],
            extraction_id="ex-010",
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )


def test_negative_block_index_rejected_on_encrypt() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_extraction_page_blocks(
            [_sample_block(-1, "a")], extraction_id="ex-011", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_duplicate_block_index_rejected_on_decrypt() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_blocks(
        [_sample_block(0, "a")], extraction_id="ex-012", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    tampered = encrypted + [dict(encrypted[0])]
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_blocks(
            tampered, extraction_id="ex-012", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_reordered_block_index_can_still_decrypt_with_correct_aad() -> None:
    """A block copied to swap another block's slot (same page, different index)
    must fail because its ciphertext was bound to its original block_index."""
    keyring = _keyring()
    encrypted = encrypt_extraction_page_blocks(
        [_sample_block(0, "a"), _sample_block(1, "b")],
        extraction_id="ex-013",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    swapped = [
        {**encrypted[0], "block_index": 1},
        {**encrypted[1], "block_index": 0},
    ]
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_blocks(
            swapped, extraction_id="ex-013", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


# 11. plaintext + encrypted coexistence failure (dual-write)
def test_read_page_text_field_rejects_coexisting_plaintext_and_encrypted() -> None:
    keyring = _keyring()
    envelope = encrypt_extraction_page_text_field(
        "본문", field_name="reviewed_text", extraction_id="ex-014", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    page_data = {"reviewed_text": "leftover plaintext", "reviewed_text_encrypted": envelope}
    with pytest.raises(ScalarDecryptionError):
        read_extraction_page_text_field(
            page_data, field_name="reviewed_text", extraction_id="ex-014", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_write_page_text_field_never_leaves_dual_write() -> None:
    keyring = _keyring()
    page_data = {"reviewed_text": "stale plaintext leftover", "other_key": "kept"}
    updated = write_extraction_page_text_field(
        page_data,
        field_name="reviewed_text",
        value="new text",
        extraction_id="ex-015",
        page_number=1,
        owner_id=OWNER_ID,
        keyring=keyring,
    )
    assert "reviewed_text" not in updated
    assert updated["other_key"] == "kept"
    assert isinstance(updated["reviewed_text_encrypted"], dict)


def test_extraction_page_blocks_reject_plaintext_and_encrypted_mixed_keys() -> None:
    keyring = _keyring()
    mixed_block = {
        "block_index": 0,
        "text": "plaintext leftover",
        "text_encrypted": {"enc_version": 1},
        "confidence": 1.0,
        "bbox": None,
        "reading_order": 0,
    }
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_blocks(
            [mixed_block], extraction_id="ex-016", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


# 12. unknown extra field failure
def test_extraction_page_blocks_reject_unknown_key_on_encrypt() -> None:
    keyring = _keyring()
    block = _sample_block(0, "본문")
    block["unexpected_field"] = "should not be here"
    with pytest.raises(ScalarEncryptionError):
        encrypt_extraction_page_blocks(
            [block], extraction_id="ex-017", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_extraction_page_blocks_reject_unknown_key_on_decrypt() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_blocks(
        [_sample_block(0, "본문")], extraction_id="ex-018", page_number=1, owner_id=OWNER_ID, keyring=keyring
    )
    encrypted[0]["unexpected_field"] = "should not be here"
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_blocks(
            encrypted, extraction_id="ex-018", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_confirmation_snapshot_page_rejects_unknown_key() -> None:
    keyring = _keyring()
    plaintext_snapshot = [
        {
            "page_id": "1",
            "page_number": 1,
            "final_text": "본문",
            "text_source": "original",
            "text_changed": False,
            "method": "direct",
            "warnings": [],
            "blocks": [],
            "unexpected_field": "nope",
        }
    ]
    with pytest.raises(ScalarEncryptionError):
        encrypt_confirmation_snapshot(
            plaintext_snapshot, extraction_id="ex-019", owner_id=OWNER_ID, snapshot_version=1, keyring=keyring
        )


# 13. legacy plaintext row fail-closed
def test_read_page_text_field_fails_closed_on_legacy_plaintext_row() -> None:
    keyring = _keyring()
    legacy_page_data = {"reviewed_text": "pre-PR-3 plaintext row"}
    with pytest.raises(ScalarDecryptionError):
        read_extraction_page_text_field(
            legacy_page_data,
            field_name="reviewed_text",
            extraction_id="ex-020",
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )


def test_decrypt_extraction_page_blocks_fails_closed_on_legacy_plaintext_block() -> None:
    keyring = _keyring()
    legacy_block = {
        "block_index": 0,
        "text": "legacy plaintext block",
        "confidence": 1.0,
        "bbox": None,
        "reading_order": 0,
    }
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_blocks(
            [legacy_block], extraction_id="ex-021", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_decrypt_confirmation_snapshot_fails_closed_on_legacy_plaintext_page() -> None:
    keyring = _keyring()
    legacy_snapshot = [
        {
            "page_id": "1",
            "page_number": 1,
            "final_text": "legacy plaintext confirmation snapshot",
            "text_source": "original",
            "text_changed": False,
            "method": "direct",
            "warnings": [],
            "blocks": [],
        }
    ]
    with pytest.raises(ScalarDecryptionError):
        decrypt_confirmation_snapshot(
            legacy_snapshot, extraction_id="ex-022", owner_id=OWNER_ID, snapshot_version=1, keyring=keyring
        )


def test_read_page_text_field_returns_none_when_never_set() -> None:
    keyring = _keyring()
    assert (
        read_extraction_page_text_field(
            {}, field_name="reviewed_text", extraction_id="ex-023", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )
        is None
    )
    assert (
        read_extraction_page_text_field(
            {"reviewed_text_encrypted": None},
            field_name="reviewed_text",
            extraction_id="ex-023",
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )
        is None
    )


def test_field_name_outside_allowlist_is_rejected() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_extraction_page_text_field(
            "본문", field_name="not_a_real_field", extraction_id="ex-024", page_number=1, owner_id=OWNER_ID, keyring=keyring
        )


def test_decrypt_errors_do_not_leak_plaintext_or_cause() -> None:
    keyring = _keyring()
    legacy_page_data = {"reviewed_text": "매우 민감한 원문 내용"}
    with pytest.raises(ScalarDecryptionError) as exc_info:
        read_extraction_page_text_field(
            legacy_page_data,
            field_name="reviewed_text",
            extraction_id="ex-025",
            page_number=1,
            owner_id=OWNER_ID,
            keyring=keyring,
        )
    message = str(exc_info.value)
    assert "매우 민감한 원문 내용" not in message
    assert OWNER_ID not in message
