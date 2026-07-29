from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


ANALYSIS_PROVIDER_REQUEST_SCHEMA_VERSION = "analysis-provider-request.v1"
ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION = "analysis-provider-response.v1"
SUPPORTED_SCHEMA_VERSIONS = {
    ANALYSIS_PROVIDER_REQUEST_SCHEMA_VERSION,
    ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
}


ANALYSIS_PROVIDER_MAX_REQUEST_BYTES = 512 * 1024
ANALYSIS_PROVIDER_MAX_RESPONSE_BYTES = 256 * 1024

MAX_CLAUSES_PER_REQUEST = 4
MAX_CANDIDATES_PER_REQUEST = 40
MAX_SOURCE_TEXT_LENGTH = 1800
MAX_FINDINGS_PER_RESPONSE = 8
MAX_QUESTIONS_PER_FINDING = 3
MAX_SUGGESTIONS_PER_FINDING = 3
MAX_STR_LEN = 800
MAX_FACT_LIST_LEN = 30


@dataclass(frozen=True)
class EvidenceCandidateInput:
    candidate_id: str
    clause_id: str
    page_number: int
    block_ids: list[str] = field(default_factory=list)
    source_text: str = ""
    start_offset: int = 0
    end_offset: int = 0
    confidence: float = 1.0

    def validate(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required.")
        if not self.clause_id:
            raise ValueError("clause_id is required.")
        if self.page_number < 1:
            raise ValueError("page_number must be positive.")
        if self.start_offset < 0 or self.end_offset < 0:
            raise ValueError("offsets must not be negative.")
        if self.end_offset < self.start_offset:
            raise ValueError("offset range is invalid.")
        if len(self.source_text) > MAX_SOURCE_TEXT_LENGTH:
            raise ValueError("source_text too long.")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0 and 1.")


@dataclass(frozen=True)
class AnalysisClauseInput:
    clause_id: str
    clause_label: str
    clause_level: str
    text: str
    page_start: int | None = None
    page_end: int | None = None
    evidence_candidates: list[EvidenceCandidateInput] = field(default_factory=list)

    def validate(self) -> None:
        if not self.clause_id:
            raise ValueError("clause_id is required.")
        if not self.clause_label:
            raise ValueError("clause_label is required.")
        if not self.text:
            raise ValueError("text is required.")
        if len(self.text) > 4000:
            raise ValueError("text too long.")
        if self.page_start is not None and self.page_start < 1:
            raise ValueError("page_start must be positive.")
        if self.page_end is not None and self.page_end < 1:
            raise ValueError("page_end must be positive.")
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end must be greater or equal than page_start.")
        for candidate in self.evidence_candidates:
            candidate.validate()


@dataclass(frozen=True)
class AnalysisProviderRequest:
    request_id: str
    document_id: str
    snapshot_version: int
    clauses: list[AnalysisClauseInput]
    document_type: str = "contract"
    language: str = "ko"
    page_ranges: list[tuple[int, int]] = field(default_factory=list)
    limits: dict[str, int] = field(default_factory=dict)
    schema_version: str = ANALYSIS_PROVIDER_REQUEST_SCHEMA_VERSION
    safety_context: str = "masked"

    def validate(self) -> None:
        if self.request_id is None or not str(self.request_id).strip():
            raise ValueError("provider_request_id_missing")
        if self.schema_version is None or not str(self.schema_version).strip():
            raise ValueError("provider_schema_version_missing")
        if self.schema_version != ANALYSIS_PROVIDER_REQUEST_SCHEMA_VERSION:
            raise ValueError("provider_schema_version_unsupported")
        if not self.document_id:
            raise ValueError("document_id_missing")
        if not isinstance(self.snapshot_version, int):
            raise ValueError("snapshot_version_invalid")
        if not self.clauses:
            raise ValueError("provider_request_invalid")
        if len(self.clauses) > MAX_CLAUSES_PER_REQUEST:
            raise ValueError("provider_clause_limit_exceeded")
        candidate_count = sum(
            len(clause.evidence_candidates) for clause in self.clauses
        )
        if candidate_count > MAX_CANDIDATES_PER_REQUEST:
            raise ValueError("provider_evidence_limit_exceeded")
        for clause in self.clauses:
            if len(clause.evidence_candidates) > MAX_CANDIDATES_PER_REQUEST:
                raise ValueError("provider_evidence_limit_exceeded")
            clause.validate()


@dataclass(frozen=True)
class AnalysisProviderQuestion:
    question_id: str
    question: str
    purpose: str
    related_evidence_candidate_ids: list[str]
    priority: str = "normal"


@dataclass(frozen=True)
class AnalysisProviderSuggestion:
    suggestion_id: str
    objective: str
    suggested_change: str
    fallback_option: str
    related_evidence_candidate_ids: list[str]
    priority: str = "normal"


@dataclass(frozen=True)
class AnalysisProviderFinding:
    finding_id: str
    category: str
    risk_type: str
    severity: str
    title: str
    summary: str
    risk_reason: str
    practical_impact: str
    action_priority: str
    selected_evidence_candidate_ids: list[str]
    questions_to_ask: list[AnalysisProviderQuestion] = field(default_factory=list)
    negotiation_suggestions: list[AnalysisProviderSuggestion] = field(
        default_factory=list
    )
    recommendation: str = ""
    expert_review_recommended: bool = False
    expert_review_reason_codes: list[str] = field(default_factory=list)
    expert_review_summary: str = ""
    confidence_score: float = 0.5
    extracted_fact_candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisProviderUsage:
    input_units: int | None = None
    output_units: int | None = None
    total_units: int | None = None
    estimated_cost_minor: int | None = None
    currency: str | None = None
    provider_reported: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        for value in (self.input_units, self.output_units, self.total_units):
            if value is not None and value < 0:
                raise ValueError("provider_usage_negative")
        if (
            self.estimated_cost_minor is not None
            and self.estimated_cost_minor < 0
        ):
            raise ValueError("provider_usage_negative")


@dataclass(frozen=True)
class AnalysisProviderResponse:
    schema_version: str
    provider_request_id: str
    findings: list[AnalysisProviderFinding]
    usage: AnalysisProviderUsage = field(default_factory=AnalysisProviderUsage)
    finish_reason: str = "stop"
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, request: AnalysisProviderRequest) -> None:
        if self.schema_version != ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION:
            raise ValueError("provider_schema_version_unsupported")
        if self.provider_request_id != request.request_id:
            raise ValueError("provider_request_id_mismatch")
        if len(self.findings) > MAX_FINDINGS_PER_RESPONSE:
            raise ValueError("provider_finding_limit_exceeded")
        if not self.findings:
            return

        allowed = {
            candidate.candidate_id
            for clause in request.clauses
            for candidate in clause.evidence_candidates
        }
        if not allowed:
            allowed = {"default"}

        finding_ids: set[str] = set()
        for finding in self.findings:
            if finding.finding_id in finding_ids:
                raise ValueError("provider_response_invalid")
            finding_ids.add(finding.finding_id)
            if not finding.finding_id:
                raise ValueError("provider_finding_id_missing")
            if not finding.selected_evidence_candidate_ids:
                raise ValueError("provider_evidence_missing")

            for candidate_id in finding.selected_evidence_candidate_ids:
                if candidate_id not in allowed:
                    raise ValueError("provider_candidate_mismatch")

            if not finding.title or not finding.summary:
                raise ValueError("provider_response_invalid")

            if len(finding.title) > MAX_STR_LEN:
                raise ValueError("provider_response_invalid")
            if len(finding.summary) > MAX_STR_LEN * 2:
                raise ValueError("provider_response_invalid")

            if len(finding.questions_to_ask) > MAX_QUESTIONS_PER_FINDING:
                raise ValueError("provider_response_invalid")
            if len(finding.negotiation_suggestions) > MAX_SUGGESTIONS_PER_FINDING:
                raise ValueError("provider_response_invalid")

            for question in finding.questions_to_ask:
                if not question.question_id:
                    raise ValueError("provider_response_invalid")
                if not question.related_evidence_candidate_ids:
                    raise ValueError("provider_evidence_missing")
                for candidate_id in question.related_evidence_candidate_ids:
                    if candidate_id not in allowed:
                        raise ValueError("provider_candidate_mismatch")

            for suggestion in finding.negotiation_suggestions:
                if not suggestion.suggestion_id:
                    raise ValueError("provider_response_invalid")
                if not suggestion.related_evidence_candidate_ids:
                    raise ValueError("provider_evidence_missing")
                for candidate_id in suggestion.related_evidence_candidate_ids:
                    if candidate_id not in allowed:
                        raise ValueError("provider_candidate_mismatch")

            if finding.expert_review_recommended and not finding.expert_review_reason_codes:
                raise ValueError("provider_response_invalid")


def request_to_json_bytes(request: AnalysisProviderRequest) -> bytes:
    payload = {
        "request_id": request.request_id,
        "document_id": request.document_id,
        "snapshot_version": request.snapshot_version,
        "schema_version": request.schema_version,
        "clauses": [
            {
                "clause_id": clause.clause_id,
                "clause_label": clause.clause_label,
                "clause_level": clause.clause_level,
                "text": clause.text,
                "page_start": clause.page_start,
                "page_end": clause.page_end,
                "evidence_candidates": [
                    {
                        "candidate_id": candidate.candidate_id,
                        "clause_id": candidate.clause_id,
                        "page_number": candidate.page_number,
                        "block_ids": candidate.block_ids,
                        "source_text": candidate.source_text,
                        "start_offset": candidate.start_offset,
                        "end_offset": candidate.end_offset,
                        "confidence": candidate.confidence,
                    }
                    for candidate in clause.evidence_candidates
                ],
            }
            for clause in request.clauses
        ],
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def response_to_json_bytes(response: AnalysisProviderResponse) -> bytes:
    payload = {
        "provider_request_id": response.provider_request_id,
        "schema_version": response.schema_version,
        "findings": [
            {
                "finding_id": finding.finding_id,
                "category": finding.category,
                "risk_type": finding.risk_type,
                "severity": finding.severity,
                "title": finding.title,
                "summary": finding.summary,
                "selected_evidence_candidate_ids": finding.selected_evidence_candidate_ids,
                "questions_to_ask": [
                    {
                        "question_id": question.question_id,
                        "question": question.question,
                        "purpose": question.purpose,
                        "related_evidence_candidate_ids": question.related_evidence_candidate_ids,
                        "priority": question.priority,
                    }
                    for question in finding.questions_to_ask
                ],
                "negotiation_suggestions": [
                    {
                        "suggestion_id": suggestion.suggestion_id,
                        "objective": suggestion.objective,
                        "suggested_change": suggestion.suggested_change,
                        "fallback_option": suggestion.fallback_option,
                        "related_evidence_candidate_ids": suggestion.related_evidence_candidate_ids,
                        "priority": suggestion.priority,
                    }
                    for suggestion in finding.negotiation_suggestions
                ],
            }
            for finding in response.findings
        ],
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
