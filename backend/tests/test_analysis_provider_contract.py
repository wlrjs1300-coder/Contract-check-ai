from __future__ import annotations

from dataclasses import replace

import pytest

from backend.app.services.analysis_provider_contract import (
    ANALYSIS_PROVIDER_MAX_REQUEST_BYTES,
    ANALYSIS_PROVIDER_MAX_RESPONSE_BYTES,
    ANALYSIS_PROVIDER_REQUEST_SCHEMA_VERSION,
    ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
    AnalysisClauseInput,
    AnalysisProviderFinding,
    AnalysisProviderQuestion,
    AnalysisProviderRequest,
    AnalysisProviderResponse,
    AnalysisProviderSuggestion,
    AnalysisProviderUsage,
    EvidenceCandidateInput,
    request_to_json_bytes,
    response_to_json_bytes,
)


def _candidate() -> EvidenceCandidateInput:
    return EvidenceCandidateInput(
        candidate_id="doc-1:clause:1-e001",
        clause_id="doc-1:clause:1",
        page_number=1,
        block_ids=["b1"],
        source_text="계약을 이행한다.",
    )


def _base_request() -> AnalysisProviderRequest:
    return AnalysisProviderRequest(
        request_id="req-1",
        document_id="doc-1",
        snapshot_version=1,
        clauses=[
            AnalysisClauseInput(
                clause_id="doc-1:clause:1",
                clause_label="제1조",
                clause_level="normal",
                text="계약을 이행한다.",
                evidence_candidates=[_candidate()],
            )
        ],
    )


def _base_finding(request: AnalysisProviderRequest) -> AnalysisProviderFinding:
    candidate_id = request.clauses[0].evidence_candidates[0].candidate_id
    return AnalysisProviderFinding(
        finding_id="finding-1",
        category="contract_clarity",
        risk_type="governance",
        severity="low",
        title="요약",
        summary="요약합니다.",
        risk_reason="",
        practical_impact="",
        action_priority="informational",
        selected_evidence_candidate_ids=[candidate_id],
        questions_to_ask=[
            AnalysisProviderQuestion(
                question_id="q-1",
                question="질문",
                purpose="확인",
                related_evidence_candidate_ids=[candidate_id],
                priority="normal",
            )
        ],
        negotiation_suggestions=[
            AnalysisProviderSuggestion(
                suggestion_id="s-1",
                objective="조치",
                suggested_change="문구 수정",
                fallback_option="No change.",
                related_evidence_candidate_ids=[candidate_id],
            )
        ],
    )


def test_request_schema_version_validation() -> None:
    request = _base_request()

    request = replace(request, schema_version="")
    with pytest.raises(ValueError, match="provider_schema_version_missing"):
        request.validate()

    request = replace(request, schema_version="analysis-provider-request.v0")
    with pytest.raises(ValueError, match="provider_schema_version_unsupported"):
        request.validate()


def test_request_payload_is_utf8_bytes() -> None:
    request = _base_request()
    raw = request_to_json_bytes(request)

    assert isinstance(raw, bytes)
    assert raw.decode("utf-8")
    assert request.schema_version == ANALYSIS_PROVIDER_REQUEST_SCHEMA_VERSION


def test_request_and_response_size_limits() -> None:
    request = _base_request()
    request_bytes = request_to_json_bytes(request)
    assert len(request_bytes) < ANALYSIS_PROVIDER_MAX_REQUEST_BYTES

    response = AnalysisProviderResponse(
        schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
        provider_request_id=request.request_id,
        findings=[_base_finding(request)],
        usage=AnalysisProviderUsage(),
    )
    response_bytes = response_to_json_bytes(response)
    assert len(response_bytes) < ANALYSIS_PROVIDER_MAX_RESPONSE_BYTES


def test_response_candidate_and_request_id_validation() -> None:
    request = _base_request()
    request.validate()

    response = AnalysisProviderResponse(
        schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
        provider_request_id=request.request_id,
        findings=[_base_finding(request)],
        usage=AnalysisProviderUsage(),
    )
    response.validate(request)

    mismatch_request_id = replace(response, provider_request_id="other")
    with pytest.raises(ValueError, match="provider_request_id_mismatch"):
        mismatch_request_id.validate(request)

    unknown_candidate = replace(
        response,
        findings=[
            _base_finding(request),
        ],
    )
    bad = unknown_candidate.findings[0]
    unknown = AnalysisProviderFinding(
        finding_id=bad.finding_id,
        category=bad.category,
        risk_type=bad.risk_type,
        severity=bad.severity,
        title=bad.title,
        summary=bad.summary,
        risk_reason=bad.risk_reason,
        practical_impact=bad.practical_impact,
        action_priority=bad.action_priority,
        selected_evidence_candidate_ids=["unknown"],
        questions_to_ask=bad.questions_to_ask,
        negotiation_suggestions=bad.negotiation_suggestions,
        recommendation=bad.recommendation,
        expert_review_recommended=bad.expert_review_recommended,
        expert_review_reason_codes=bad.expert_review_reason_codes,
        expert_review_summary=bad.expert_review_summary,
        confidence_score=bad.confidence_score,
        extracted_fact_candidates=bad.extracted_fact_candidates,
    )

    bad_response = replace(response, findings=[unknown])
    with pytest.raises(ValueError, match="provider_candidate_mismatch"):
        bad_response.validate(request)
