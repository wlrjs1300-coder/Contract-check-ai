from uuid import uuid4

import pytest

from backend.app.db.models import AnalysisJob, Clause, Document
from backend.app.services.analysis_provider import AnalysisProviderInput
from backend.app.services.analysis_pipeline import run_analysis_pipeline
from backend.app.services.analysis_result_schema import (
    ALLOWED_EXPERT_REVIEW_CODES,
    AnalysisResultData,
)


def _create_document_and_clause(db_session, body: str):
    document_id = str(uuid4())
    document = Document(
        id=document_id,
        filename="facts.txt",
        content_type="text/plain",
        size_bytes=len(body),
        character_count=len(body),
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )
    clause = Clause(
        id=str(uuid4()),
        clause_id="clause-001",
        reference_id=f"{document_id}:clause:1",
        source_hash="hash",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title="사실 항목 테스트",
        body=body,
        warnings=[],
    )
    document.clauses.append(clause)
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    db_session.refresh(clause)
    return document, clause


def _provider_with_items(items):
    class Provider:
        def analyze_clause(
            self,
            provider_input: AnalysisProviderInput,
        ) -> AnalysisResultData:
            expert_review_recommended = items.get("expert_review_recommended", False)
            return AnalysisResultData(
                reference_id=provider_input.reference_id,
                display_label="안전",
                summary="고객 가치 분석 결과",
                expert_review_recommended=expert_review_recommended,
                finding_id=f"{provider_input.reference_id}-finding-001",
                category="contract_clarity",
                risk_type="governance",
                severity="low",
                title="계약 사실 검증",
                risk_reason="리스크 기반 점검 항목입니다.",
                practical_impact="추가 확인이 필요할 수 있습니다.",
                action_priority="informational",
                questions_to_ask=items.get("questions_to_ask", []),
                negotiation_suggestions=items.get("negotiation_suggestions", []),
                recommendation="추가 확인을 진행하세요.",
                expert_review_reason_codes=items.get("expert_review_reason_codes", []),
                expert_review_summary=items.get("expert_review_summary", ""),
                confidence_score=0.8,
                evidence=items.get("evidence", []),
                extracted_facts=items.get("extracted_facts", []),
                validation_status="verified",
                is_stale=False,
            )

    return Provider()


def test_pipeline_stores_normalized_extracted_facts(db_session) -> None:
    _, clause = _create_document_and_clause(db_session, "계약 기간 및 금액 조항")
    evidence_id = f"{clause.reference_id}-e001"
    provider = _provider_with_items(
        {
            "evidence": [{"evidence_id": evidence_id}],
            "questions_to_ask": [
                {
                    "question_id": "q-1",
                    "question": "계약일 조정 규정을 확인해야 하나요?",
                    "purpose": "계약기간 계산 확인",
                    "related_evidence_ids": [evidence_id],
                    "priority": "normal",
                }
            ],
            "negotiation_suggestions": [
                {
                    "suggestion_id": "s-1",
                    "objective": "조기 종료 조건 정리",
                    "suggested_change": "종료 통지 기간 추가",
                    "fallback_option": "통지 조항 삭제 검토",
                    "related_evidence_ids": [evidence_id],
                    "priority": "high",
                }
            ],
            "extracted_facts": [
                {
                    "fact_id": "f-1",
                    "fact_type": "contract_start_date",
                    "label": "계약일",
                    "value": "2026.07.21",
                    "normalized_value": "2026.07.21",
                    "unit": "",
                    "date_value": "2026.07.21",
                    "amount_value": "3,000,000원",
                    "currency": "",
                    "duration_value": "",
                    "obligation_party": "user",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.85,
                },
                {
                    "fact_id": "f-2",
                    "fact_type": "contract_start_date",
                    "label": "계약일 상대",
                    "value": "계약일로부터 30일",
                    "normalized_value": "계약일로부터 30일",
                    "unit": "",
                    "date_value": "계약일로부터 30일",
                    "amount_value": "",
                    "currency": "",
                    "duration_value": "",
                    "obligation_party": "user",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.81,
                },
                {
                    "fact_id": "f-3",
                    "fact_type": "payment_amount",
                    "label": "계약금액",
                    "value": "300만원",
                    "normalized_value": "300만원",
                    "unit": "만원",
                    "date_value": "",
                    "amount_value": "",
                    "currency": "",
                    "duration_value": "",
                    "obligation_party": "contractor",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.9,
                },
                {
                    "fact_id": "f-4",
                    "fact_type": "penalty",
                    "label": "위약금 비율",
                    "value": "10%",
                    "normalized_value": "10%",
                    "unit": "%",
                    "date_value": "",
                    "amount_value": "",
                    "currency": "",
                    "duration_value": "",
                    "obligation_party": "",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.82,
                },
                {
                    "fact_id": "f-5",
                    "fact_type": "obligation",
                    "label": "부가세 별도",
                    "value": "부가세 별도",
                    "normalized_value": "부가세 별도",
                    "unit": "",
                    "date_value": "",
                    "amount_value": "",
                    "currency": "",
                    "duration_value": "",
                    "obligation_party": "",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.8,
                },
            ],
        }
    )

    job = AnalysisJob(id=str(uuid4()), document_id=clause.document_id, status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    run_analysis_pipeline(db=db_session, job=job, clauses=[clause], provider=provider)

    db_session.refresh(job)
    assert job.status == "completed"
    analysis_value = job.result_items[0].extra_data["analysis_value"]

    assert analysis_value["evidence"][0]["evidence_id"] == evidence_id
    assert analysis_value["extracted_facts"][0]["date_value"] == "2026-07-21"
    assert analysis_value["extracted_facts"][2]["amount_value"] == "3000000"
    assert analysis_value["extracted_facts"][2]["currency"] == "KRW"
    assert analysis_value["extracted_facts"][3]["amount_value"] == ""
    assert analysis_value["extracted_facts"][3]["status"] == "verified"
    assert analysis_value["extracted_facts"][4]["obligation_party"] == "unspecified"
    assert analysis_value["extracted_facts"][4]["status"] == "ambiguous"
    assert analysis_value["extracted_facts"][1]["date_value"] == "계약일로부터 30일"


def test_pipeline_rejects_question_without_related_evidence(db_session) -> None:
    _, clause = _create_document_and_clause(db_session, "질문 근거 누락")
    evidence_id = f"{clause.reference_id}-e001"
    provider = _provider_with_items(
        {
            "evidence": [{"evidence_id": evidence_id}],
            "questions_to_ask": [
                {
                    "question_id": "q-1",
                    "question": "근거 없이 질문",
                    "purpose": "재확인",
                    "related_evidence_ids": [],
                    "priority": "high",
                }
            ],
        }
    )

    job = AnalysisJob(id=str(uuid4()), document_id=clause.document_id, status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError, match="question_evidence_missing"):
        run_analysis_pipeline(db=db_session, job=job, clauses=[clause], provider=provider)


def test_pipeline_rejects_suggestion_without_related_evidence(db_session) -> None:
    _, clause = _create_document_and_clause(db_session, "제안 근거 누락")
    evidence_id = f"{clause.reference_id}-e001"
    provider = _provider_with_items(
        {
            "evidence": [{"evidence_id": evidence_id}],
            "negotiation_suggestions": [
                {
                    "suggestion_id": "s-1",
                    "objective": "제안",
                    "suggested_change": "조건 삭제",
                    "fallback_option": "차선 제안",
                    "related_evidence_ids": [],
                    "priority": "normal",
                }
            ],
        }
    )

    job = AnalysisJob(id=str(uuid4()), document_id=clause.document_id, status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError, match="suggestion_evidence_missing"):
        run_analysis_pipeline(db=db_session, job=job, clauses=[clause], provider=provider)


def test_pipeline_rejects_fact_without_evidence(db_session) -> None:
    _, clause = _create_document_and_clause(db_session, "사실 근거 누락")
    evidence_id = f"{clause.reference_id}-e001"
    provider = _provider_with_items(
        {
            "evidence": [{"evidence_id": evidence_id}],
            "extracted_facts": [
                {
                    "fact_id": "f-1",
                    "fact_type": "contract_start_date",
                    "label": "시작일",
                    "value": "2026-01-01",
                    "normalized_value": "2026-01-01",
                    "unit": "",
                    "date_value": "2026-01-01",
                    "amount_value": "",
                    "currency": "KRW",
                    "duration_value": "",
                    "obligation_party": "user",
                    "status": "verified",
                    "evidence": [],
                    "confidence_score": 0.8,
                }
            ],
        }
    )

    job = AnalysisJob(id=str(uuid4()), document_id=clause.document_id, status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError, match="fact_evidence_missing"):
        run_analysis_pipeline(db=db_session, job=job, clauses=[clause], provider=provider)


def test_pipeline_rejects_invalid_expert_review_code(db_session) -> None:
    _, clause = _create_document_and_clause(db_session, "전문가 검토 코드 테스트")
    evidence_id = f"{clause.reference_id}-e001"
    provider = _provider_with_items(
        {
            "evidence": [{"evidence_id": evidence_id}],
            "expert_review_reason_codes": ["invalid_code"],
            "expert_review_recommended": True,
            "expert_review_summary": "요약",
            "extracted_facts": [
                {
                    "fact_id": "f-1",
                    "fact_type": "contract_start_date",
                    "label": "시작일",
                    "value": "2026-01-01",
                    "normalized_value": "2026-01-01",
                    "unit": "",
                    "date_value": "2026-01-01",
                    "amount_value": "",
                    "currency": "KRW",
                    "duration_value": "",
                    "obligation_party": "user",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.8,
                }
            ],
        }
    )

    job = AnalysisJob(id=str(uuid4()), document_id=clause.document_id, status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError, match="unsupported expert_review_reason_code"):
        run_analysis_pipeline(db=db_session, job=job, clauses=[clause], provider=provider)


def test_pipeline_rejects_missing_expert_review_summary_or_reason_code(db_session) -> None:
    _, clause = _create_document_and_clause(db_session, "전문가 리뷰 미완료")
    evidence_id = f"{clause.reference_id}-e001"

    provider_missing_reason = _provider_with_items(
        {
            "evidence": [{"evidence_id": evidence_id}],
            "expert_review_recommended": True,
            "expert_review_summary": "",
            "expert_review_reason_codes": [],
            "extracted_facts": [
                {
                    "fact_id": "f-1",
                    "fact_type": "contract_start_date",
                    "label": "시작일",
                    "value": "2026-01-01",
                    "normalized_value": "2026-01-01",
                    "unit": "",
                    "date_value": "2026-01-01",
                    "amount_value": "",
                    "currency": "KRW",
                    "duration_value": "",
                    "obligation_party": "user",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.8,
                }
            ],
        }
    )

    job = AnalysisJob(id=str(uuid4()), document_id=clause.document_id, status="queued")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError, match="expert_review_reason_codes required"):
        run_analysis_pipeline(
            db=db_session,
            job=job,
            clauses=[clause],
            provider=provider_missing_reason,
        )

    provider_missing_summary = _provider_with_items(
        {
            "evidence": [{"evidence_id": evidence_id}],
            "expert_review_recommended": True,
            "expert_review_reason_codes": [list(ALLOWED_EXPERT_REVIEW_CODES)[0]],
            "expert_review_summary": "",
            "extracted_facts": [
                {
                    "fact_id": "f-1",
                    "fact_type": "contract_start_date",
                    "label": "시작일",
                    "value": "2026-01-01",
                    "normalized_value": "2026-01-01",
                    "unit": "",
                    "date_value": "2026-01-01",
                    "amount_value": "",
                    "currency": "KRW",
                    "duration_value": "",
                    "obligation_party": "user",
                    "status": "verified",
                    "evidence": [{"evidence_id": evidence_id}],
                    "confidence_score": 0.8,
                }
            ],
        }
    )

    job2 = AnalysisJob(id=str(uuid4()), document_id=clause.document_id, status="queued")
    db_session.add(job2)
    db_session.commit()
    db_session.refresh(job2)
    with pytest.raises(ValueError, match="expert_review_summary is required"):
        run_analysis_pipeline(
            db=db_session,
            job=job2,
            clauses=[clause],
            provider=provider_missing_summary,
        )
