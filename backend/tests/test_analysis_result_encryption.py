from __future__ import annotations
from backend.tests.support import encrypted_document, encrypted_clause

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.models import AnalysisJob
from backend.app.services.analysis_pipeline import run_analysis_pipeline
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    ScalarEncryptionError,
    encrypt_clause_body,
)
from backend.app.services.analysis_result_encryption import (
    decrypt_analysis_value,
    encrypt_analysis_value,
)
from backend.tests.support import TEST_USER_ID


def _keyring():
    return get_encryption_keyring()


def _analysis_value(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "category": "termination",
        "risk_type": "termination",
        "severity": "medium",
        "title": "해지 통지 조건 확인 필요",
        "risk_reason": "해지 통지 기간이 명시돼 있지 않습니다.",
        "practical_impact": "예상보다 이른 해지 통보를 받을 수 있습니다.",
        "action_priority": "negotiate",
        "questions_to_ask": [
            {
                "question_id": "q-1",
                "question": "해지 통지 기간은 며칠인가요?",
                "purpose": "계약 종료 시점 확인",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "q-1",
            }
        ],
        "negotiation_suggestions": [
            {
                "suggestion_id": "s-1",
                "objective": "통지 기간 명확화",
                "suggested_change": "30일 사전 통지 조항 추가",
                "fallback_option": "구두 합의로 대체",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "high",
                "id": "s-1",
            }
        ],
        "recommendation": "해지 통지 조항을 서면으로 확정하세요.",
        "confidence_score": 0.8,
        "evidence": [{"evidence_id": "ref:clause:1-e001"}],
        "extracted_facts": [
            {
                "fact_id": "f-1",
                "fact_type": "payment_amount",
                "label": "월 임대료",
                "value": "1,000,000원",
                "normalized_value": "1000000",
                "unit": "원",
                "date_value": "",
                "amount_value": "1000000",
                "currency": "KRW",
                "duration_value": "",
                "obligation_party": "user",
                "status": "verified",
                "evidence": [{"evidence_id": "ref:clause:1-e001"}],
                "confidence_score": 0.85,
            }
        ],
        "validation_status": "verified",
        "expert_review_reason_codes": [],
        "expert_review_summary": "",
        "is_stale": False,
    }
    value.update(overrides)
    return value


def _identity(**overrides: object) -> dict[str, str]:
    identity = {
        "analysis_job_id": "job-1",
        "clause_record_id": "clause-1",
        "owner_id": "owner-1",
    }
    identity.update(overrides)
    return identity


def test_analysis_value_round_trip() -> None:
    plaintext = _analysis_value()
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    decrypted = decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())
    assert decrypted == plaintext


def test_encrypted_payload_never_contains_plaintext_text_fields() -> None:
    plaintext = _analysis_value()
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())

    assert "title" not in encrypted
    assert "risk_reason" not in encrypted
    assert "practical_impact" not in encrypted
    assert "recommendation" not in encrypted
    assert "expert_review_summary" not in encrypted
    assert encrypted["title_encrypted"]["ciphertext"]
    assert plaintext["title"] not in str(encrypted)

    question = encrypted["questions_to_ask"][0]
    assert "question" not in question
    assert "purpose" not in question
    assert plaintext["questions_to_ask"][0]["question"] not in str(encrypted)

    suggestion = encrypted["negotiation_suggestions"][0]
    assert "objective" not in suggestion
    assert plaintext["negotiation_suggestions"][0]["objective"] not in str(encrypted)

    fact = encrypted["extracted_facts"][0]
    for field_name in (
        "label",
        "value",
        "normalized_value",
        "date_value",
        "amount_value",
        "duration_value",
        "obligation_party",
    ):
        assert field_name not in fact
        assert f"{field_name}_encrypted" in fact


def test_same_plaintext_produces_different_ciphertext() -> None:
    plaintext = _analysis_value()
    first = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    second = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    assert first["title_encrypted"]["ciphertext"] != second["title_encrypted"]["ciphertext"]


def test_tampered_ciphertext_fails() -> None:
    encrypted = encrypt_analysis_value(_analysis_value(), keyring=_keyring(), **_identity())
    encrypted["title_encrypted"] = dict(encrypted["title_encrypted"])
    encrypted["title_encrypted"]["ciphertext"] = encrypted["risk_reason_encrypted"]["ciphertext"]
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_wrong_owner_fails() -> None:
    encrypted = encrypt_analysis_value(_analysis_value(), keyring=_keyring(), **_identity())
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(
            encrypted,
            keyring=_keyring(),
            **_identity(owner_id="other-owner"),
        )


def test_wrong_analysis_job_id_fails() -> None:
    encrypted = encrypt_analysis_value(_analysis_value(), keyring=_keyring(), **_identity())
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(
            encrypted,
            keyring=_keyring(),
            **_identity(analysis_job_id="job-2"),
        )


def test_wrong_clause_record_id_fails() -> None:
    encrypted = encrypt_analysis_value(_analysis_value(), keyring=_keyring(), **_identity())
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(
            encrypted,
            keyring=_keyring(),
            **_identity(clause_record_id="clause-2"),
        )


def test_title_and_recommendation_ciphertext_cannot_be_swapped() -> None:
    encrypted = encrypt_analysis_value(_analysis_value(), keyring=_keyring(), **_identity())
    encrypted["title_encrypted"], encrypted["recommendation_encrypted"] = (
        encrypted["recommendation_encrypted"],
        encrypted["title_encrypted"],
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_question_ciphertext_cannot_be_copied_to_a_different_question_id() -> None:
    plaintext = _analysis_value(
        questions_to_ask=[
            {
                "question_id": "q-1",
                "question": "질문 1",
                "purpose": "목적 1",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "q-1",
            },
            {
                "question_id": "q-2",
                "question": "질문 2",
                "purpose": "목적 2",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "q-2",
            },
        ]
    )
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    encrypted["questions_to_ask"][1]["question_encrypted"] = encrypted["questions_to_ask"][0][
        "question_encrypted"
    ]
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_reordering_question_list_still_decrypts() -> None:
    plaintext = _analysis_value(
        questions_to_ask=[
            {
                "question_id": "q-1",
                "question": "질문 1",
                "purpose": "목적 1",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "q-1",
            },
            {
                "question_id": "q-2",
                "question": "질문 2",
                "purpose": "목적 2",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "q-2",
            },
        ]
    )
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    encrypted["questions_to_ask"] = list(reversed(encrypted["questions_to_ask"]))
    decrypted = decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())
    assert {q["question_id"]: q["question"] for q in decrypted["questions_to_ask"]} == {
        "q-1": "질문 1",
        "q-2": "질문 2",
    }


def test_suggestion_ciphertext_cannot_be_copied_across_suggestion_id() -> None:
    plaintext = _analysis_value(
        negotiation_suggestions=[
            {
                "suggestion_id": "s-1",
                "objective": "목표 1",
                "suggested_change": "변경 1",
                "fallback_option": "대안 1",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "s-1",
            },
            {
                "suggestion_id": "s-2",
                "objective": "목표 2",
                "suggested_change": "변경 2",
                "fallback_option": "대안 2",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "s-2",
            },
        ]
    )
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    encrypted["negotiation_suggestions"][0]["objective_encrypted"] = encrypted[
        "negotiation_suggestions"
    ][1]["objective_encrypted"]
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_fact_ciphertext_cannot_be_copied_across_fact_id() -> None:
    plaintext = _analysis_value(
        extracted_facts=[
            {
                "fact_id": "f-1",
                "fact_type": "payment_amount",
                "label": "월 임대료",
                "value": "1,000,000원",
                "normalized_value": "1000000",
                "unit": "원",
                "date_value": "",
                "amount_value": "1000000",
                "currency": "KRW",
                "duration_value": "",
                "obligation_party": "user",
                "status": "verified",
                "evidence": [{"evidence_id": "ref:clause:1-e001"}],
                "confidence_score": 0.85,
            },
            {
                "fact_id": "f-2",
                "fact_type": "deposit",
                "label": "보증금",
                "value": "5,000,000원",
                "normalized_value": "5000000",
                "unit": "원",
                "date_value": "",
                "amount_value": "5000000",
                "currency": "KRW",
                "duration_value": "",
                "obligation_party": "user",
                "status": "verified",
                "evidence": [{"evidence_id": "ref:clause:1-e001"}],
                "confidence_score": 0.85,
            },
        ]
    )
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    encrypted["extracted_facts"][0]["value_encrypted"] = encrypted["extracted_facts"][1][
        "value_encrypted"
    ]
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_dual_write_rejected_on_encrypt() -> None:
    plaintext = _analysis_value()
    encrypted = dict(encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity()))
    encrypted["title"] = "leftover plaintext"
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_legacy_plaintext_row_fails_closed() -> None:
    legacy = _analysis_value()
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(legacy, keyring=_keyring(), **_identity())


def test_unknown_top_level_key_rejected_on_encrypt() -> None:
    plaintext = _analysis_value()
    plaintext["unexpected_field"] = "x"
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())


def test_missing_top_level_key_rejected_on_encrypt() -> None:
    plaintext = _analysis_value()
    del plaintext["title"]
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())


def test_unknown_key_in_question_rejected_on_encrypt() -> None:
    plaintext = _analysis_value()
    plaintext["questions_to_ask"][0]["extra"] = "x"
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())


def test_empty_question_id_rejected_on_encrypt() -> None:
    plaintext = _analysis_value()
    plaintext["questions_to_ask"][0]["question_id"] = ""
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())


def test_duplicate_question_id_rejected_on_encrypt() -> None:
    plaintext = _analysis_value(
        questions_to_ask=[
            {
                "question_id": "q-1",
                "question": "질문 1",
                "purpose": "목적 1",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "q-1",
            },
            {
                "question_id": "q-1",
                "question": "질문 2",
                "purpose": "목적 2",
                "related_evidence_ids": ["ref:clause:1-e001"],
                "priority": "normal",
                "id": "q-1",
            },
        ]
    )
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())


def test_duplicate_fact_id_rejected_on_encrypt() -> None:
    fact = _analysis_value()["extracted_facts"][0]
    plaintext = _analysis_value(extracted_facts=[fact, dict(fact)])
    with pytest.raises(ScalarEncryptionError):
        encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())


def test_empty_facts_and_lists_round_trip() -> None:
    plaintext = _analysis_value(
        questions_to_ask=[],
        negotiation_suggestions=[],
        extracted_facts=[],
    )
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    decrypted = decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())
    assert decrypted == plaintext


def test_empty_string_text_fields_round_trip() -> None:
    plaintext = _analysis_value(title="", risk_reason="", expert_review_summary="")
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    decrypted = decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())
    assert decrypted["title"] == ""
    assert decrypted["risk_reason"] == ""
    assert decrypted["expert_review_summary"] == ""


def test_decrypt_errors_do_not_leak_plaintext_or_cause() -> None:
    plaintext = _analysis_value()
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    with pytest.raises(ScalarDecryptionError) as excinfo:
        decrypt_analysis_value(
            encrypted,
            keyring=_keyring(),
            **_identity(owner_id="other-owner"),
        )
    message = str(excinfo.value)
    assert plaintext["title"] not in message
    assert plaintext["risk_reason"] not in message


def test_raw_database_never_stores_plaintext_analysis_value_text(
    db_session: Session,
) -> None:
    """Runs the real pipeline end to end and inspects the raw ORM row (not the
    API response) to confirm title/risk_reason/practical_impact/recommendation/
    expert_review_summary and question/suggestion/fact text are stored only as
    `_encrypted` envelopes, never as plaintext strings."""
    document_id = str(uuid4())
    keyring = get_encryption_keyring()
    clause_id = str(uuid4())
    body = "월세는 매월 1일 지급하며 지연 시 지연이자가 발생한다."

    document = encrypted_document(
        id=document_id,
        owner_id=TEST_USER_ID,
        filename="raw-db-check.txt",
        content_type="text/plain",
        size_bytes=10,
        character_count=10,
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )
    clause = encrypted_clause(
        id=clause_id,
        clause_id="clause-001",
        reference_id=f"{document_id}:clause:1",
        source_hash="test-source-hash",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title=None,
        body_encrypted=encrypt_clause_body(
            body,
            clause_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
    )
    document.clauses.append(clause)
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.refresh(clause)

    job = AnalysisJob(id=str(uuid4()), document_id=document.id, status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    run_analysis_pipeline(db_session, job, [clause])
    assert job.status == "completed"

    raw_value = job.result_items[0].extra_data["analysis_value"]

    for plaintext_key in (
        "title",
        "risk_reason",
        "practical_impact",
        "recommendation",
        "expert_review_summary",
    ):
        assert plaintext_key not in raw_value
        assert f"{plaintext_key}_encrypted" in raw_value

    for question in raw_value["questions_to_ask"]:
        assert "question" not in question
        assert "purpose" not in question
        assert "question_encrypted" in question
        assert "purpose_encrypted" in question
    for suggestion in raw_value["negotiation_suggestions"]:
        assert "objective" not in suggestion
        assert "objective_encrypted" in suggestion
    for fact in raw_value["extracted_facts"]:
        for field_name in (
            "label",
            "value",
            "normalized_value",
            "date_value",
            "amount_value",
            "duration_value",
            "obligation_party",
        ):
            assert field_name not in fact
            assert f"{field_name}_encrypted" in fact


def test_normalized_fact_ciphertext_rejects_cross_field_swap() -> None:
    encrypted = encrypt_analysis_value(
        _analysis_value(), keyring=_keyring(), **_identity()
    )
    fact = encrypted["extracted_facts"][0]
    fact["date_value_encrypted"] = fact["amount_value_encrypted"]
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_normalized_fact_ciphertext_rejects_cross_fact_swap() -> None:
    fact = _analysis_value()["extracted_facts"][0]
    other = dict(fact)
    other["fact_id"] = "f-2"
    other["normalized_value"] = "different"
    encrypted = encrypt_analysis_value(
        _analysis_value(extracted_facts=[fact, other]),
        keyring=_keyring(),
        **_identity(),
    )
    encrypted["extracted_facts"][0]["normalized_value_encrypted"] = encrypted[
        "extracted_facts"
    ][1]["normalized_value_encrypted"]
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_normalized_fact_plaintext_legacy_fails_closed() -> None:
    encrypted = encrypt_analysis_value(
        _analysis_value(), keyring=_keyring(), **_identity()
    )
    fact = encrypted["extracted_facts"][0]
    fact["normalized_value"] = "legacy plaintext"
    with pytest.raises(ScalarDecryptionError):
        decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())


def test_normalized_fact_null_values_are_preserved() -> None:
    fact = dict(_analysis_value()["extracted_facts"][0])
    for field_name in (
        "normalized_value",
        "date_value",
        "amount_value",
        "duration_value",
        "obligation_party",
    ):
        fact[field_name] = None
    plaintext = _analysis_value(extracted_facts=[fact])
    encrypted = encrypt_analysis_value(plaintext, keyring=_keyring(), **_identity())
    decrypted = decrypt_analysis_value(encrypted, keyring=_keyring(), **_identity())
    assert decrypted == plaintext
