from __future__ import annotations

import os

from backend.app.services.analysis_provider_contract import (
    AnalysisProviderFinding,
    AnalysisProviderQuestion,
    AnalysisProviderRequest,
    ANALYSIS_PROVIDER_MAX_RESPONSE_BYTES,
    AnalysisProviderResponse,
    AnalysisProviderSuggestion,
    AnalysisProviderUsage,
    ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
)
from backend.app.services.provider_execution import (
    ProviderExecutionError,
    ProviderFailureReason,
)


class FakeAnalysisProvider:
    provider_name = "fake"
    provider_version = "0.0.0"

    MODES = {
        "success",
        "timeout",
        "rate_limit",
        "temporary_failure",
        "permanent_failure",
        "invalid_schema",
        "unsupported_schema_version",
        "request_id_mismatch",
        "unknown_candidate",
        "duplicate_candidate",
        "empty_evidence",
        "missing_required_field",
        "oversized_response",
        "too_many_findings",
    }

    mode_to_reason = {
        "timeout": ProviderFailureReason.PROVIDER_TIMEOUT,
        "rate_limit": ProviderFailureReason.PROVIDER_RATE_LIMITED,
        "temporary_failure": ProviderFailureReason.PROVIDER_TEMPORARY_FAILURE,
        "permanent_failure": ProviderFailureReason.PROVIDER_PERMANENT_FAILURE,
    }

    def analyze(self, request: AnalysisProviderRequest) -> AnalysisProviderResponse:
        mode = (os.getenv("FAKE_ANALYSIS_PROVIDER_MODE", "success").strip().lower()
                or "success")

        if mode not in self.MODES:
            mode = "success"

        if mode in self.mode_to_reason:
            reason = self.mode_to_reason[mode]
            retryable = reason in {
                ProviderFailureReason.PROVIDER_TIMEOUT,
                ProviderFailureReason.PROVIDER_RATE_LIMITED,
                ProviderFailureReason.PROVIDER_TEMPORARY_FAILURE,
            }
            raise ProviderExecutionError(reason, retryable=retryable, message=f"fake provider: {mode}")

        return self._response_for_mode(mode, request)

    def _response_for_mode(
        self,
        mode: str,
        request: AnalysisProviderRequest,
    ) -> AnalysisProviderResponse:
        candidate_id = (
            request.clauses[0].evidence_candidates[0].candidate_id
            if request.clauses and request.clauses[0].evidence_candidates
            else "default"
        )

        if mode == "unsupported_schema_version":
            return AnalysisProviderResponse(
                schema_version="analysis-provider-response.v0",
                provider_request_id=request.request_id,
                findings=[_build_finding(request, candidate_id, candidate_id="missing")],
                usage=_default_usage(),
            )

        if mode == "request_id_mismatch":
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=f"{request.request_id}-mismatch",
                findings=[_build_finding(request, candidate_id)],
                usage=_default_usage(),
            )

        if mode == "unknown_candidate":
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=request.request_id,
                findings=[_build_finding(request, "unknown-candidate")],
                usage=_default_usage(),
            )

        if mode == "duplicate_candidate":
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=request.request_id,
                findings=[
                    _build_finding(
                        request, candidate_id, candidate_id=f"{candidate_id}"
                    ),
                    _build_finding(
                        request, candidate_id, candidate_id=f"{candidate_id}"
                    ),
                ],
                usage=_default_usage(),
            )

        if mode == "empty_evidence":
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=request.request_id,
                findings=[_build_finding(request, candidate_id, selected_empty=True)],
                usage=_default_usage(),
            )

        if mode == "missing_required_field":
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=request.request_id,
                findings=[_build_finding(request, candidate_id, title="")],
                usage=_default_usage(),
            )

        if mode == "invalid_schema":
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=request.request_id,
                findings=[
                    AnalysisProviderFinding(
                        finding_id=f"{request.clauses[0].clause_id}-fake-1",
                        category="contract_clarity",
                        risk_type="governance",
                        severity="info",
                        title="Invalid schema mode",
                        summary="",
                        risk_reason="",
                        practical_impact="",
                        action_priority="informational",
                        selected_evidence_candidate_ids=[candidate_id],
                        questions_to_ask=[
                            AnalysisProviderQuestion(
                                question_id="q-fake",
                                question="Invalid schema",
                                purpose="Sanity check",
                                related_evidence_candidate_ids=[candidate_id],
                                priority="normal",
                            )
                        ],
                        negotiation_suggestions=[
                            AnalysisProviderSuggestion(
                                suggestion_id="s-fake",
                                objective="Add clarification",
                                suggested_change="Request explicit date.",
                                fallback_option="No change.",
                                related_evidence_candidate_ids=[candidate_id],
                                priority="normal",
                            )
                        ],
                    )
                ],
                usage=AnalysisProviderUsage(
                    input_units=-1,
                    output_units=-1,
                    total_units=-1,
                    estimated_cost_minor=-1,
                    currency="KRW",
                    provider_reported={"fake": True},
                ),
            )

        if mode == "oversized_response":
            huge_question = "x" * (ANALYSIS_PROVIDER_MAX_RESPONSE_BYTES)
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=request.request_id,
                findings=[
                    AnalysisProviderFinding(
                        finding_id=f"{request.clauses[0].clause_id}-fake-oversize",
                        category="contract_clarity",
                        risk_type="governance",
                        severity="info",
                        title="Oversized response mode",
                        summary="Synthetic oversized response marker.",
                        risk_reason="",
                        practical_impact="",
                        action_priority="informational",
                        selected_evidence_candidate_ids=[candidate_id],
                        questions_to_ask=[
                            AnalysisProviderQuestion(
                                question_id="q-overflow",
                                question=huge_question,
                                purpose="force response payload size",
                                related_evidence_candidate_ids=[candidate_id],
                                priority="normal",
                            )
                        ],
                        negotiation_suggestions=[
                            AnalysisProviderSuggestion(
                                suggestion_id="s-overflow",
                                objective="Ensure size limit enforcement.",
                                suggested_change="N/A",
                                fallback_option="N/A",
                                related_evidence_candidate_ids=[candidate_id],
                                priority="normal",
                            )
                        ],
                    )
                ],
                usage=_default_usage(),
            )

        if mode == "too_many_findings":
            findings = [
                _build_finding(request, candidate_id, suffix=f"{idx:03d}")
                for idx in range(1, 20)
            ]
            return AnalysisProviderResponse(
                schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
                provider_request_id=request.request_id,
                findings=findings,
                usage=_default_usage(),
                finish_reason="length",
                provider_metadata={"provider": "fake"},
            )

        return AnalysisProviderResponse(
            schema_version=ANALYSIS_PROVIDER_RESPONSE_SCHEMA_VERSION,
            provider_request_id=request.request_id,
            findings=[_build_finding(request, candidate_id)],
            usage=_default_usage(),
            finish_reason="stop",
            provider_metadata={"provider": "fake"},
        )


def _build_finding(
    request: AnalysisProviderRequest,
    candidate_id: str,
    candidate_id_value: str | None = None,
    selected_empty: bool = False,
    title: str = "Faked risk candidate",
    summary: str = "Fake provider result.",
    suffix: str = "1",
) -> AnalysisProviderFinding:
    selected = [] if selected_empty else [candidate_id_value or candidate_id]
    return AnalysisProviderFinding(
        finding_id=f"{request.clauses[0].clause_id}-fake-{suffix}",
        category="contract_clarity",
        risk_type="governance",
        severity="info",
        title=title,
        summary=summary,
        risk_reason="",
        practical_impact="",
        action_priority="informational",
        selected_evidence_candidate_ids=selected,
        questions_to_ask=[
            AnalysisProviderQuestion(
                question_id="q-fake",
                question="Is this clause consistent with other terms?",
                purpose="Sanity check",
                related_evidence_candidate_ids=[candidate_id_value or candidate_id],
                priority="normal",
            )
        ],
        negotiation_suggestions=[
            AnalysisProviderSuggestion(
                suggestion_id="s-fake",
                objective="Add clarification",
                suggested_change="Request explicit date.",
                fallback_option="No change.",
                related_evidence_candidate_ids=[candidate_id_value or candidate_id],
                priority="normal",
            )
        ],
    )


def _default_usage(estimated_cost_minor: int = 0) -> AnalysisProviderUsage:
    return AnalysisProviderUsage(
        input_units=5,
        output_units=6,
        total_units=11,
        estimated_cost_minor=estimated_cost_minor,
        currency="KRW",
        provider_reported={"fake": True},
    )
