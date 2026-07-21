from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Protocol

from backend.app.services.analysis_provider_contract import (
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
)
from backend.app.services.analysis_result_schema import AnalysisResultData


@dataclass(frozen=True)
class AnalysisProviderInput:
    reference_id: str
    masked_text: str


class AnalysisProvider(Protocol):
    def analyze(self, request: AnalysisProviderRequest) -> AnalysisProviderResponse:
        ...


def _ensure_non_empty_request_id(value: str) -> str:
    return value.strip() if value.strip() else str(uuid.uuid4())


def response_from_legacy_result(
    request: AnalysisProviderRequest,
    provider_input: AnalysisProviderInput,
    result: AnalysisResultData,
) -> AnalysisProviderResponse:
    finding_id = result.finding_id or f"{provider_input.reference_id}-finding"

    question_list = [
        AnalysisProviderQuestion(
            question_id=str(item.get("question_id", "")),
            question=str(item.get("question", "")),
            purpose=str(item.get("purpose", "")),
            related_evidence_candidate_ids=[
                str(candidate_id)
                for candidate_id in item.get("related_evidence_ids", ["default"])
                if isinstance(candidate_id, str) and candidate_id.strip()
            ],
            priority=str(item.get("priority", "normal")),
        )
        for item in (
            result.questions_to_ask if isinstance(result.questions_to_ask, list) else []
        )
        if isinstance(item, dict)
    ]

    suggestion_list = [
        AnalysisProviderSuggestion(
            suggestion_id=str(item.get("suggestion_id", "")),
            objective=str(item.get("objective", "")),
            suggested_change=str(item.get("suggested_change", "")),
            fallback_option=str(item.get("fallback_option", "")),
            related_evidence_candidate_ids=[
                str(candidate_id)
                for candidate_id in item.get("related_evidence_ids", ["default"])
                if isinstance(candidate_id, str) and candidate_id.strip()
            ],
            priority=str(item.get("priority", "normal")),
        )
        for item in (
            result.negotiation_suggestions
            if isinstance(result.negotiation_suggestions, list)
            else []
        )
        if isinstance(item, dict)
    ]

    clause_candidate_ids = [
        candidate.candidate_id
        for clause in request.clauses
        for candidate in clause.evidence_candidates
    ]
    selected = clause_candidate_ids[:1] if clause_candidate_ids else ["default"]

    finding = AnalysisProviderFinding(
        finding_id=finding_id,
        category=result.category,
        risk_type=result.risk_type,
        severity=result.severity,
        title=result.title,
        summary=result.summary,
        risk_reason=result.risk_reason,
        practical_impact=result.practical_impact,
        action_priority=result.action_priority,
        selected_evidence_candidate_ids=selected,
        questions_to_ask=question_list,
        negotiation_suggestions=suggestion_list,
        recommendation=result.recommendation,
        expert_review_recommended=bool(result.expert_review_recommended),
        expert_review_reason_codes=result.expert_review_reason_codes,
        expert_review_summary=result.expert_review_summary,
        confidence_score=float(result.confidence_score),
        extracted_fact_candidates=list(result.extracted_facts),
    )

    return AnalysisProviderResponse(
        schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
        provider_request_id=request.request_id,
        findings=[finding],
        usage=AnalysisProviderUsage(),
        provider_metadata={"legacy_source": "analysis_result_data"},
    )


def request_from_legacy_input(
    document_id: str,
    snapshot_version: int,
    provider_input: AnalysisProviderInput,
    evidence_candidates: list[dict[str, object]],
) -> AnalysisProviderRequest:
    candidates = [
        EvidenceCandidateInput(
            candidate_id=str(evidence.get("evidence_id", "default")),
            clause_id=provider_input.reference_id,
            page_number=int(evidence.get("page_number", 1) or 1),
            block_ids=[
                str(block_id)
                for block_id in evidence.get("block_ids", [])
                if isinstance(block_id, str) and block_id.strip()
            ],
            source_text=str(evidence.get("source_text", ""))[:1800],
            start_offset=int(evidence.get("start_offset", 0) or 0),
            end_offset=int(evidence.get("end_offset", 0) or 0),
            confidence=float(evidence.get("confidence", 1.0))
            if isinstance(evidence.get("confidence"), (int, float))
            else 1.0,
        )
        for evidence in evidence_candidates
    ]

    clause_input = AnalysisClauseInput(
        clause_id=provider_input.reference_id,
        clause_label="clause",
        clause_level="normal",
        text=provider_input.masked_text[:4000],
        evidence_candidates=candidates,
    )

    return AnalysisProviderRequest(
        request_id=_ensure_non_empty_request_id(f"{document_id}:{provider_input.reference_id}"),
        document_id=document_id,
        snapshot_version=snapshot_version,
        clauses=[clause_input],
        schema_version=ANALYSIS_PROVIDER_REQUEST_SCHEMA_VERSION,
        safety_context="masked",
    )


class ExternalAnalysisProviderUnavailable:
    @property
    def provider_name(self) -> str:
        return "unavailable"

    @property
    def provider_version(self) -> str:
        return "0"

    def analyze(
        self,
        request: AnalysisProviderRequest,
    ) -> AnalysisProviderResponse:
        raise RuntimeError("analysis provider unavailable")


class SyntheticAnalysisProvider:
    provider_name = "synthetic"
    provider_version = "0.7.0"

    def analyze(
        self,
        request: AnalysisProviderRequest,
    ) -> AnalysisProviderResponse:
        first_clause = request.clauses[0]

        category = "contract_clarity"
        severity = "low"
        action_priority = "informational"

        candidate_ids = [
            candidate.candidate_id
            for candidate in first_clause.evidence_candidates
        ] or ["default"]

        risk_type = "governance"
        if "termination" in first_clause.text:
            category = "termination"
            risk_type = "termination"
            severity = "medium"
            action_priority = "negotiate"
        elif "payment" in first_clause.text:
            category = "payment"
            risk_type = "financial"
            severity = "high"
            action_priority = "before_signing"

        finding = AnalysisProviderFinding(
            finding_id=f"{first_clause.clause_id}-finding-001",
            category=category,
            risk_type=risk_type,
            severity=severity,
            title="Clause review candidate",
            summary="합성 분석 결과입니다.",
            risk_reason="Potential risk needs validation.",
            practical_impact="Review this clause before signature.",
            action_priority=action_priority,
            selected_evidence_candidate_ids=candidate_ids,
            questions_to_ask=[
                AnalysisProviderQuestion(
                    question_id="q1",
                    question="Any hidden obligations exist?",
                    purpose="Check ambiguous wording.",
                    related_evidence_candidate_ids=[candidate_ids[0]],
                    priority="normal",
                )
            ],
            negotiation_suggestions=[
                AnalysisProviderSuggestion(
                    suggestion_id="s1",
                    objective="Adjust clarity",
                    suggested_change="Insert explicit exception.",
                    fallback_option="Keep as-is and confirm with other section.",
                    related_evidence_candidate_ids=[candidate_ids[0]],
                    priority="normal",
                )
            ],
            recommendation="Please confirm with other section.",
            expert_review_recommended=False,
            expert_review_reason_codes=[],
            extracted_fact_candidates=[],
            confidence_score=0.72,
        )

        return AnalysisProviderResponse(
            schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
            provider_request_id=request.request_id,
            findings=[finding],
            usage=AnalysisProviderUsage(
                input_units=10,
                output_units=15,
                total_units=25,
                estimated_cost_minor=0,
                currency="KRW",
                provider_reported={"adapter": "synthetic"},
            ),
            finish_reason="stop",
            provider_metadata={"provider": "synthetic"},
        )

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        request = AnalysisProviderRequest(
            request_id=f"legacy:{provider_input.reference_id}",
            document_id="legacy-doc",
            snapshot_version=1,
            clauses=[
                AnalysisClauseInput(
                    clause_id=provider_input.reference_id,
                    clause_label="clause",
                    clause_level="normal",
                    text=provider_input.masked_text,
                    evidence_candidates=[
                        EvidenceCandidateInput(
                            candidate_id="default",
                            clause_id=provider_input.reference_id,
                            page_number=1,
                            source_text=provider_input.masked_text,
                        )
                    ],
                )
            ],
        )
        response = self.analyze(request)
        first_finding = response.findings[0]
        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary="Synthetic provider result.",
            expert_review_recommended=first_finding.expert_review_recommended,
            finding_id=first_finding.finding_id,
            category=first_finding.category,
            risk_type=first_finding.risk_type,
            severity=first_finding.severity,
            title=first_finding.title,
            risk_reason=first_finding.risk_reason,
            practical_impact=first_finding.practical_impact,
            action_priority=first_finding.action_priority,
            questions_to_ask=[
                {
                    "question_id": q.question_id,
                    "question": q.question,
                    "purpose": q.purpose,
                    "related_evidence_ids": q.related_evidence_candidate_ids,
                    "priority": q.priority,
                }
                for q in first_finding.questions_to_ask
            ],
            negotiation_suggestions=[
                {
                    "suggestion_id": s.suggestion_id,
                    "objective": s.objective,
                    "suggested_change": s.suggested_change,
                    "fallback_option": s.fallback_option,
                    "related_evidence_ids": s.related_evidence_candidate_ids,
                    "priority": s.priority,
                }
                for s in first_finding.negotiation_suggestions
            ],
            recommendation=first_finding.recommendation,
            expert_review_reason_codes=first_finding.expert_review_reason_codes,
            expert_review_summary=first_finding.expert_review_summary,
            confidence_score=first_finding.confidence_score,
            extracted_facts=first_finding.extracted_fact_candidates,
            validation_status="verified",
            is_stale=False,
        )


DEFAULT_ANALYSIS_PROVIDER: AnalysisProvider = SyntheticAnalysisProvider()


def normalize_provider_result(
    provider: AnalysisProvider,
    request: AnalysisProviderRequest,
    provider_input: AnalysisProviderInput,
    result: AnalysisProviderResponse | AnalysisResultData,
) -> AnalysisProviderResponse:
    if isinstance(result, AnalysisProviderResponse):
        return result
    if isinstance(result, AnalysisResultData):
        return response_from_legacy_result(
            request=request,
            provider_input=provider_input,
            result=result,
        )
    raise TypeError("Provider result type is unsupported.")


@dataclass(frozen=True)
class AnalysisProviderConfig:
    provider_name: str
    provider_version: str


def _env_mode() -> str:
    return (os.getenv("APP_ENV", "test").strip().lower() or "test")


def analysis_result_data_from_provider_response(
    provider_input: AnalysisProviderInput,
    response: AnalysisProviderResponse,
) -> AnalysisResultData:
    finding = response.findings[0] if response.findings else None
    if finding is None:
        raise ValueError("Provider returned no finding.")

    return AnalysisResultData(
        reference_id=provider_input.reference_id,
        display_label="추가 확인",
        summary=finding.summary,
        expert_review_recommended=finding.expert_review_recommended,
        finding_id=finding.finding_id,
        category=finding.category,
        risk_type=finding.risk_type,
        severity=finding.severity,
        title=finding.title,
        risk_reason=finding.risk_reason,
        practical_impact=finding.practical_impact,
        action_priority=finding.action_priority,
        questions_to_ask=[
            {
                "question_id": question.question_id,
                "question": question.question,
                "purpose": question.purpose,
                "related_evidence_ids": question.related_evidence_candidate_ids,
                "priority": question.priority,
            }
            for question in finding.questions_to_ask
        ],
        negotiation_suggestions=[
            {
                "suggestion_id": suggestion.suggestion_id,
                "objective": suggestion.objective,
                "suggested_change": suggestion.suggested_change,
                "fallback_option": suggestion.fallback_option,
                "related_evidence_ids": suggestion.related_evidence_candidate_ids,
                "priority": suggestion.priority,
            }
            for suggestion in finding.negotiation_suggestions
        ],
        recommendation=finding.recommendation,
        expert_review_reason_codes=finding.expert_review_reason_codes,
        expert_review_summary=finding.expert_review_summary,
        confidence_score=finding.confidence_score,
        extracted_facts=finding.extracted_fact_candidates,
        validation_status="verified",
        is_stale=False,
    )
