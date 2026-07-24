from __future__ import annotations

import base64
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.crypto import EncryptionEnvelope, EnvelopeValidationError
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.models import (
    AnalysisJob,
    AnalysisResultItem,
    Clause,
    Document,
    Extraction,
    ExtractionPage,
)
from backend.app.main import app
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    ScalarEncryptionError,
    _build_canonical_record_id,
    decrypt_analysis_result_summary,
    decrypt_clause_body,
    decrypt_extraction_page_text,
    encrypt_analysis_result_summary,
    encrypt_clause_body,
    encrypt_extraction_page_text,
)
from backend.tests.support import TEST_USER_ID


def _keyring():
    return get_encryption_keyring()


def test_clause_body_round_trip() -> None:
    keyring = _keyring()
    plaintext = "조항 본문 내용입니다. 월세는 1,000,000원입니다."
    encrypted = encrypt_clause_body(
        plaintext,
        clause_id="clause-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )

    envelope = EncryptionEnvelope.from_json(encrypted)
    mapping = envelope.to_mapping()
    assert set(mapping.keys()) == {
        "enc_version",
        "key_id",
        "algorithm",
        "nonce",
        "ciphertext",
    }
    assert decrypt_clause_body(
        encrypted,
        clause_id="clause-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    ) == plaintext


def test_extraction_page_text_round_trip() -> None:
    keyring = _keyring()
    plaintext = "이미지 OCR 추출 텍스트입니다. 2026-07-21 계약일입니다."
    encrypted = encrypt_extraction_page_text(
        plaintext,
        extraction_id="22222222-2222-4222-8222-222222222222",
        page_number=3,
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    assert decrypt_extraction_page_text(
        encrypted,
        extraction_id="22222222-2222-4222-8222-222222222222",
        page_number=3,
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    ) == plaintext


def test_analysis_result_summary_round_trip() -> None:
    keyring = _keyring()
    plaintext = "손해배상 관련 핵심 조항이 누락되어 있습니다."
    encrypted = encrypt_analysis_result_summary(
        plaintext,
        analysis_job_id="44444444-4444-4444-8444-444444444444",
        clause_record_id="clause-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    assert decrypt_analysis_result_summary(
        encrypted,
        analysis_job_id="44444444-4444-4444-8444-444444444444",
        clause_record_id="clause-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    ) == plaintext


def test_utf8_korean_round_trip() -> None:
    keyring = _keyring()
    plaintext = "문서 본문에 한글이 안전하게 저장됩니다. 특수문자: ©, ™, 한자: 漢字"
    encrypted = encrypt_clause_body(
        plaintext,
        clause_id="k-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    assert decrypt_clause_body(
        encrypted,
        clause_id="k-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    ) == plaintext


def test_wrong_clause_identifier_is_rejected() -> None:
    keyring = _keyring()
    encrypted = encrypt_clause_body(
        "계약 조항",
        clause_id="clause-right",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_body(
            encrypted,
            clause_id="clause-wrong",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_wrong_owner_identifier_is_rejected() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_text(
        "페이지 텍스트",
        extraction_id="ex-001",
        page_number=1,
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            encrypted,
            extraction_id="ex-001",
            page_number=1,
            owner_id="22222222-2222-4222-8222-222222222222",
            keyring=keyring,
        )


def test_wrong_extraction_context_is_rejected() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_text(
        "페이지 텍스트",
        extraction_id="ex-ctx",
        page_number=1,
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            encrypted,
            extraction_id="ex-ctx",
            page_number=2,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_wrong_summary_context_is_rejected() -> None:
    keyring = _keyring()
    encrypted = encrypt_analysis_result_summary(
        "요약 텍스트",
        analysis_job_id="job-001",
        clause_record_id="clause-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            encrypted,
            analysis_job_id="job-001",
            clause_record_id="clause-002",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_invalid_envelope_payload_is_rejected() -> None:
    keyring = _keyring()
    encrypted = encrypt_clause_body(
        "본문",
        clause_id="c-1",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    envelope = json.loads(encrypted)
    envelope["nonce"] = "not-base64"
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_body(
            json.dumps(envelope, ensure_ascii=False),
            clause_id="c-1",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_double_encryption_is_blocked() -> None:
    keyring = _keyring()
    encrypted = encrypt_clause_body(
        "plain",
        clause_id="c-double",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarEncryptionError):
        encrypt_clause_body(
            encrypted,
            clause_id="c-double",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_tampered_ciphertext_or_unknown_key_is_rejected() -> None:
    keyring = _keyring()
    encrypted = encrypt_analysis_result_summary(
        "요약",
        analysis_job_id="job-001",
        clause_record_id="clause-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    envelope = json.loads(encrypted)

    decoded = base64.b64decode(envelope["ciphertext"])
    decoded = bytes(decoded[:-1] + bytes([decoded[-1] ^ 0xFF]))
    envelope["ciphertext"] = base64.b64encode(decoded).decode("ascii")
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            json.dumps(envelope, ensure_ascii=False),
            analysis_job_id="job-001",
            clause_record_id="clause-001",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )

    envelope["key_id"] = "unknown-key-id"
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            json.dumps(envelope, ensure_ascii=False),
            analysis_job_id="job-001",
            clause_record_id="clause-001",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_envelope_validation_rejects_invalid_json_or_duplicates() -> None:
    valid = '{"enc_version":1,"key_id":"synthetic-key-v1","algorithm":"AES-256-GCM","nonce":"eA==","ciphertext":"AAAAAAAAAAAAAAAAAAAAAA=="}'
    # malformed JSON
    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope.from_json("not-json")

    # top-level non-dict
    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope.from_json("[1,2,3]")

    # duplicate keys should be rejected
    duplicate_key_json = (
        '{"enc_version":1,"key_id":"synthetic-key-v1","algorithm":"AES-256-GCM",'
        '"nonce":"eA==","ciphertext":"AAAAAA==","nonce":"bQ==","ciphertext":"BBBBBB=="}'
    )
    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope.from_json(duplicate_key_json)

    mapping = json.loads(valid)
    mapping["extra"] = "x"
    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope.from_mapping(mapping)


def test_composite_record_id_is_stable_and_disambiguated() -> None:
    first = _build_canonical_record_id({"extraction_id": "e-1", "page_number": 1})
    second = _build_canonical_record_id({"page_number": 1, "extraction_id": "e-1"})
    assert first == second
    assert first == '{"extraction_id":"e-1","page_number":1}'

    third = _build_canonical_record_id({"analysis_job_id": "job-1", "clause_record_id": "99"})
    assert third == '{"analysis_job_id":"job-1","clause_record_id":"99"}'


def test_encrypt_analysis_result_summary_rejects_non_string_clause_record_id() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_result_summary(
            "요약",
            analysis_job_id="job-001",
            clause_record_id=99,  # type: ignore[arg-type]
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_page_number_type_and_invalid_records_are_rejected() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_extraction_page_text(
            "텍스트",
            extraction_id="ex-002",
            page_number=0,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )

    with pytest.raises(ScalarEncryptionError):
        encrypt_extraction_page_text(
            "텍스트",
            extraction_id="ex-002",
            page_number=1.2,  # type: ignore[arg-type]
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_reject_null_byte_identifiers_and_plaintext() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_clause_body(
            "본문",
            clause_id="clause\x00bad",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )

    encrypted = encrypt_clause_body(
        "본문",
        clause_id="clause-safe",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_body(
            encrypted,
            clause_id="clause\x00bad",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


@pytest.mark.parametrize("bad_value", ["", " leading", "trailing ", " both "])
def test_encrypt_clause_body_rejects_invalid_clause_id(bad_value: str) -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_clause_body(
            "본문",
            clause_id=bad_value,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


@pytest.mark.parametrize("bad_value", ["", " leading", "trailing ", " both "])
def test_encrypt_clause_body_rejects_invalid_owner_id(bad_value: str) -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_clause_body(
            "본문",
            clause_id="clause-valid",
            owner_id=bad_value,
            keyring=keyring,
        )


@pytest.mark.parametrize("bad_value", ["", " leading", "trailing ", " both "])
def test_encrypt_extraction_page_text_rejects_invalid_extraction_id(bad_value: str) -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_extraction_page_text(
            "텍스트",
            extraction_id=bad_value,
            page_number=1,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


@pytest.mark.parametrize("bad_value", ["", " leading", "trailing ", " both "])
def test_encrypt_analysis_result_summary_rejects_invalid_analysis_job_id(bad_value: str) -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_result_summary(
            "요약",
            analysis_job_id=bad_value,
            clause_record_id="clause-001",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


@pytest.mark.parametrize("bad_value", ["", " leading", "trailing ", " both "])
def test_encrypt_analysis_result_summary_rejects_invalid_clause_record_id(bad_value: str) -> None:
    keyring = _keyring()
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_result_summary(
            "요약",
            analysis_job_id="job-001",
            clause_record_id=bad_value,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_decrypt_extraction_page_text_rejects_null_byte_identifiers() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_text(
        "텍스트",
        extraction_id="ex-safe",
        page_number=1,
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            encrypted,
            extraction_id="ex\x00bad",
            page_number=1,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            encrypted,
            extraction_id="ex-safe",
            page_number=1,
            owner_id="owner\x00bad",
            keyring=keyring,
        )


def test_decrypt_analysis_result_summary_rejects_null_byte_identifiers() -> None:
    keyring = _keyring()
    encrypted = encrypt_analysis_result_summary(
        "요약",
        analysis_job_id="job-safe",
        clause_record_id="clause-safe",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            encrypted,
            analysis_job_id="job\x00bad",
            clause_record_id="clause-safe",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            encrypted,
            analysis_job_id="job-safe",
            clause_record_id="clause\x00bad",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            encrypted,
            analysis_job_id="job-safe",
            clause_record_id="clause-safe",
            owner_id="owner\x00bad",
            keyring=keyring,
        )


def test_decrypt_rejects_non_string_encrypted_value() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_body(
            None,  # type: ignore[arg-type]
            clause_id="clause-001",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            123,  # type: ignore[arg-type]
            extraction_id="ex-001",
            page_number=1,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            b"bytes-not-str",  # type: ignore[arg-type]
            analysis_job_id="job-001",
            clause_record_id="clause-001",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_decrypt_rejects_non_string_identifier_types() -> None:
    keyring = _keyring()
    encrypted = encrypt_clause_body(
        "본문",
        clause_id="clause-001",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_body(
            encrypted,
            clause_id=123,  # type: ignore[arg-type]
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_body(
            encrypted,
            clause_id="clause-001",
            owner_id=None,  # type: ignore[arg-type]
            keyring=keyring,
        )


def test_decrypt_extraction_page_text_rejects_invalid_page_number_type() -> None:
    keyring = _keyring()
    encrypted = encrypt_extraction_page_text(
        "텍스트",
        extraction_id="ex-001",
        page_number=1,
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            encrypted,
            extraction_id="ex-001",
            page_number=1.5,  # type: ignore[arg-type]
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            encrypted,
            extraction_id="ex-001",
            page_number=0,
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )


def test_decrypt_failure_does_not_leak_cause() -> None:
    keyring = _keyring()
    with pytest.raises(ScalarDecryptionError) as exc_info:
        decrypt_clause_body(
            "not-json",
            clause_id="clause-001",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
    assert exc_info.value.__cause__ is None
    assert "not-json" not in str(exc_info.value)


def test_double_encryption_check_does_not_flag_padded_envelope_lookalike() -> None:
    keyring = _keyring()
    encrypted = encrypt_clause_body(
        "본문",
        clause_id="clause-pad",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    padded = f" {encrypted} "

    # A padded lookalike is not an exact valid envelope, so it must be treated
    # as ordinary plaintext rather than rejected as double encryption.
    re_encrypted = encrypt_clause_body(
        padded,
        clause_id="clause-pad-2",
        owner_id="11111111-1111-4111-8111-111111111111",
        keyring=keyring,
    )
    assert (
        decrypt_clause_body(
            re_encrypted,
            clause_id="clause-pad-2",
            owner_id="11111111-1111-4111-8111-111111111111",
            keyring=keyring,
        )
        == padded
    )


def test_raw_database_never_stores_plaintext_scalars(
    db_session: Session,
    sqlite_test_engine,
) -> None:
    keyring = _keyring()
    clause_plaintext = "Synthetic clause body for raw-storage check."
    page_plaintext = "Synthetic extraction page text for raw-storage check."
    summary_plaintext = "Synthetic analysis summary for raw-storage check."

    document_id = str(uuid4())
    clause_id = str(uuid4())
    document = Document(
        id=document_id,
        owner_id=TEST_USER_ID,
        filename="raw-storage.sample.txt",
        content_type="text/plain",
        size_bytes=10,
        character_count=10,
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )
    clause = Clause(
        id=clause_id,
        clause_id="clause-001",
        reference_id=f"{document_id}:clause:1",
        source_hash="hash",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            clause_plaintext,
            clause_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
    )
    document.clauses.append(clause)
    db_session.add(document)

    extraction_id = str(uuid4())
    extraction = Extraction(
        id=extraction_id,
        owner_id=TEST_USER_ID,
        filename_display="raw-storage.pdf",
        source_type="pdf",
        size_bytes=10,
        page_count=1,
        status="confirmed",
        method="pdf",
        warnings=[],
        requires_user_review=False,
        extra_data={},
    )
    page = ExtractionPage(
        extraction_id=extraction_id,
        page_number=1,
        method="pdf",
        text_encrypted=encrypt_extraction_page_text(
            page_plaintext,
            extraction_id=extraction_id,
            page_number=1,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
        requires_user_review=False,
        extra_data={},
    )
    extraction.pages.append(page)
    db_session.add(extraction)

    job_id = str(uuid4())
    job = AnalysisJob(id=job_id, document_id=document_id, status="completed")
    db_session.add(job)
    db_session.flush()

    result_item = AnalysisResultItem(
        analysis_job_id=job_id,
        clause_record_id=clause_id,
        reference_id=clause.reference_id,
        display_label="주의",
        summary_encrypted=encrypt_analysis_result_summary(
            summary_plaintext,
            analysis_job_id=job_id,
            clause_record_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        expert_review_recommended=False,
        extra_data={},
    )
    db_session.add(result_item)
    db_session.commit()

    with sqlite_test_engine.connect() as conn:
        clause_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(clauses)")).fetchall()
        }
        page_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(extraction_pages)")).fetchall()
        }
        item_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(analysis_result_items)")).fetchall()
        }

        raw_body = conn.execute(
            text("SELECT body_encrypted FROM clauses WHERE id = :id"),
            {"id": clause_id},
        ).scalar_one()
        raw_text = conn.execute(
            text("SELECT text_encrypted FROM extraction_pages WHERE extraction_id = :id"),
            {"id": extraction_id},
        ).scalar_one()
        raw_summary = conn.execute(
            text("SELECT summary_encrypted FROM analysis_result_items WHERE analysis_job_id = :id"),
            {"id": job_id},
        ).scalar_one()

    assert "body" not in clause_columns
    assert "body_encrypted" in clause_columns
    assert "text" not in page_columns
    assert "text_encrypted" in page_columns
    assert "summary" not in item_columns
    assert "summary_encrypted" in item_columns

    assert clause_plaintext not in raw_body
    assert page_plaintext not in raw_text
    assert summary_plaintext not in raw_summary

    for raw_value in (raw_body, raw_text, raw_summary):
        envelope = EncryptionEnvelope.from_json(raw_value)
        assert set(envelope.to_mapping().keys()) == {
            "enc_version",
            "key_id",
            "algorithm",
            "nonce",
            "ciphertext",
        }

    client = TestClient(app)
    document_response = client.get(f"/documents/{document_id}")
    assert document_response.status_code == 200
    document_response_text = document_response.text
    assert clause_plaintext in document_response_text
    assert "ciphertext" not in document_response_text
    assert "nonce" not in document_response_text
    assert "key_id" not in document_response_text

    results_response = client.get(f"/documents/{document_id}/analysis-results")
    assert results_response.status_code == 200
    results_response_text = results_response.text
    assert summary_plaintext in results_response_text
    assert "ciphertext" not in results_response_text
    assert "nonce" not in results_response_text
    assert "key_id" not in results_response_text


def test_clause_row_copy_cross_row_decryption_fails(db_session: Session) -> None:
    keyring = _keyring()
    document_id = str(uuid4())
    document = Document(
        id=document_id,
        owner_id=TEST_USER_ID,
        filename="row-copy.sample.txt",
        content_type="text/plain",
        size_bytes=10,
        character_count=10,
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )
    clause_a_id = str(uuid4())
    clause_b_id = str(uuid4())
    clause_a = Clause(
        id=clause_a_id,
        clause_id="clause-a",
        reference_id=f"{document_id}:clause:1",
        source_hash="hash-a",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            "Clause A body.",
            clause_id=clause_a_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
    )
    clause_b = Clause(
        id=clause_b_id,
        clause_id="clause-b",
        reference_id=f"{document_id}:clause:2",
        source_hash="hash-b",
        ordinal=2,
        marker="2.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            "Clause B body.",
            clause_id=clause_b_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
    )
    document.clauses.extend([clause_a, clause_b])
    db_session.add(document)
    db_session.commit()
    db_session.refresh(clause_a)
    db_session.refresh(clause_b)

    # Simulate a row-copy attack: clause B's ciphertext column now holds clause A's value.
    clause_b.body_encrypted = clause_a.body_encrypted
    db_session.commit()
    db_session.refresh(clause_b)

    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_body(
            clause_b.body_encrypted,
            clause_id=clause_b.id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        )


def test_extraction_page_row_copy_cross_row_decryption_fails(db_session: Session) -> None:
    keyring = _keyring()
    extraction_id = str(uuid4())
    extraction = Extraction(
        id=extraction_id,
        owner_id=TEST_USER_ID,
        filename_display="row-copy.pdf",
        source_type="pdf",
        size_bytes=10,
        page_count=2,
        status="confirmed",
        method="pdf",
        warnings=[],
        requires_user_review=False,
        extra_data={},
    )
    page_a = ExtractionPage(
        extraction_id=extraction_id,
        page_number=1,
        method="pdf",
        text_encrypted=encrypt_extraction_page_text(
            "Page A text.",
            extraction_id=extraction_id,
            page_number=1,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
        requires_user_review=False,
        extra_data={},
    )
    page_b = ExtractionPage(
        extraction_id=extraction_id,
        page_number=2,
        method="pdf",
        text_encrypted=encrypt_extraction_page_text(
            "Page B text.",
            extraction_id=extraction_id,
            page_number=2,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
        requires_user_review=False,
        extra_data={},
    )
    extraction.pages.extend([page_a, page_b])
    db_session.add(extraction)
    db_session.commit()
    db_session.refresh(page_a)
    db_session.refresh(page_b)

    # Simulate a row-copy attack: page B's ciphertext column now holds page A's value.
    page_b.text_encrypted = page_a.text_encrypted
    db_session.commit()
    db_session.refresh(page_b)

    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_page_text(
            page_b.text_encrypted,
            extraction_id=page_b.extraction_id,
            page_number=page_b.page_number,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        )


def test_analysis_result_item_row_copy_cross_row_decryption_fails(db_session: Session) -> None:
    keyring = _keyring()
    document_id = str(uuid4())
    document = Document(
        id=document_id,
        owner_id=TEST_USER_ID,
        filename="row-copy-item.sample.txt",
        content_type="text/plain",
        size_bytes=10,
        character_count=10,
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )
    clause_id = str(uuid4())
    clause = Clause(
        id=clause_id,
        clause_id="clause-001",
        reference_id=f"{document_id}:clause:1",
        source_hash="hash",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            "Clause body.",
            clause_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
    )
    document.clauses.append(clause)
    db_session.add(document)
    db_session.flush()

    job_a_id = str(uuid4())
    job_b_id = str(uuid4())
    job_a = AnalysisJob(id=job_a_id, document_id=document_id, status="completed")
    job_b = AnalysisJob(id=job_b_id, document_id=document_id, status="completed")
    db_session.add_all([job_a, job_b])
    db_session.flush()

    item_a = AnalysisResultItem(
        analysis_job_id=job_a_id,
        clause_record_id=clause_id,
        reference_id=clause.reference_id,
        display_label="주의",
        summary_encrypted=encrypt_analysis_result_summary(
            "Item A summary.",
            analysis_job_id=job_a_id,
            clause_record_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        expert_review_recommended=False,
        extra_data={},
    )
    item_b = AnalysisResultItem(
        analysis_job_id=job_b_id,
        clause_record_id=clause_id,
        reference_id=clause.reference_id,
        display_label="주의",
        summary_encrypted=encrypt_analysis_result_summary(
            "Item B summary.",
            analysis_job_id=job_b_id,
            clause_record_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        expert_review_recommended=False,
        extra_data={},
    )
    db_session.add_all([item_a, item_b])
    db_session.commit()
    db_session.refresh(item_a)
    db_session.refresh(item_b)

    # Simulate a row-copy attack: item B's ciphertext column now holds item A's value.
    item_b.summary_encrypted = item_a.summary_encrypted
    db_session.commit()
    db_session.refresh(item_b)

    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_result_summary(
            item_b.summary_encrypted,
            analysis_job_id=item_b.analysis_job_id,
            clause_record_id=item_b.clause_record_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        )


def test_wrong_owner_context_decryption_fails_without_leaking_details() -> None:
    keyring = _keyring()
    owner_a = "11111111-1111-4111-8111-111111111111"
    owner_b = "22222222-2222-4222-8222-222222222222"
    encrypted = encrypt_clause_body(
        "Owner A clause body.",
        clause_id="clause-owner-check",
        owner_id=owner_a,
        keyring=keyring,
    )

    with pytest.raises(ScalarDecryptionError) as exc_info:
        decrypt_clause_body(
            encrypted,
            clause_id="clause-owner-check",
            owner_id=owner_b,
            keyring=keyring,
        )

    message = str(exc_info.value)
    assert owner_a not in message
    assert owner_b not in message
    assert "Owner A clause body." not in message
