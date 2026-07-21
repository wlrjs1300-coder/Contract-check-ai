from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from backend.app.services.analysis_provider import AnalysisProvider, AnalysisProviderInput
from backend.app.services.analysis_provider_contract import (
    AnalysisProviderFinding,
    AnalysisProviderQuestion,
    AnalysisProviderRequest,
    AnalysisProviderResponse,
    AnalysisProviderSuggestion,
    AnalysisProviderUsage,
    ANALYSIS_PROVIDER_MAX_REQUEST_BYTES,
    ANALYSIS_PROVIDER_MAX_RESPONSE_BYTES,
    request_to_json_bytes,
    response_to_json_bytes,
)
from backend.app.services.analysis_result_schema import AnalysisResultData


class ProviderFailureReason:
    # legacy test-facing reasons
    TIMEOUT = "PROVIDER_TIMEOUT"
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    UNKNOWN = "PROVIDER_UNKNOWN_ERROR"
    INVALID_RESPONSE = "provider_response_invalid"
    RETRY_EXHAUSTED = "provider_retry_exhausted"

    # v0.7 contract reasons
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TEMPORARY_FAILURE = "provider_temporary_failure"
    PROVIDER_RETRY_EXHAUSTED = "provider_retry_exhausted"
    PROVIDER_PERMANENT_FAILURE = "provider_permanent_failure"
    PROVIDER_REQUEST_TOO_LARGE = "provider_request_too_large"
    PROVIDER_RESPONSE_TOO_LARGE = "provider_response_too_large"


class ProviderExecutionError(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        *,
        retryable: bool,
        message: str = "Provider execution failed.",
        attempt_number: int | None = None,
        request_id: str | None = None,
        raw_payload: bytes | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.retryable = retryable
        self.attempt_number = attempt_number
        self.request_id = request_id
        self.raw_payload = raw_payload


class ProviderTimeoutError(ProviderExecutionError):
    def __init__(self, message: str = "Provider execution failed.") -> None:
        super().__init__(
            ProviderFailureReason.TIMEOUT,
            retryable=True,
            message=message,
        )


class ProviderRateLimitError(ProviderExecutionError):
    def __init__(self, message: str = "Provider execution failed.") -> None:
        super().__init__(
            ProviderFailureReason.RATE_LIMITED,
            retryable=True,
            message=message,
        )


class ProviderAuthenticationError(ProviderExecutionError):
    def __init__(self, message: str = "Provider authentication failed.") -> None:
        super().__init__(
            ProviderFailureReason.AUTHENTICATION_ERROR,
            retryable=False,
            message=message,
        )


class ProviderRetryExhausted(ProviderExecutionError):
    def __init__(
        self,
        message: str = "Provider retry attempts exceeded.",
        *,
        attempts: int,
        request_id: str | None = None,
        last_reason_code: str | None = None,
    ) -> None:
        super().__init__(
            ProviderFailureReason.PROVIDER_RETRY_EXHAUSTED,
            retryable=False,
            message=message,
        )
        self.attempts = attempts
        self.request_id = request_id
        self.last_reason_code = last_reason_code


class ProviderInvalidResponseError(ProviderExecutionError):
    def __init__(self) -> None:
        super().__init__(
            ProviderFailureReason.INVALID_RESPONSE,
            retryable=False,
        )


@dataclass(frozen=True)
class ProviderExecutionPolicy:
    max_attempts: int = 1
    backoff_seconds: tuple[float, ...] = ()

    def validate(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")

        if any(delay < 0 for delay in self.backoff_seconds):
            raise ValueError("backoff_seconds must not be negative.")

    def delay_before_attempt(self, attempt_number: int) -> float:
        delay_index = attempt_number - 2
        if delay_index < 0:
            return 0.0
        if delay_index >= len(self.backoff_seconds):
            return 0.0
        return self.backoff_seconds[delay_index]


DEFAULT_PROVIDER_EXECUTION_POLICY = ProviderExecutionPolicy()


def _coerce_provider_error(exc: Exception) -> ProviderExecutionError:
    if isinstance(exc, ProviderExecutionError):
        return exc

    reason_message = str(exc).lower()
    if "authentication" in reason_message or "unauthorized" in reason_message:
        return ProviderAuthenticationError()
    if "timeout" in reason_message:
        return ProviderTimeoutError()
    if "ratelimit" in reason_message or "rate limit" in reason_message:
        return ProviderRateLimitError()

    return ProviderExecutionError(
        ProviderFailureReason.UNKNOWN,
        retryable=False,
    )


def _legacy_result_to_provider_response(
    request: AnalysisProviderRequest,
    result: AnalysisResultData,
) -> AnalysisProviderResponse:
    candidate_id = (
        request.clauses[0].evidence_candidates[0].candidate_id
        if request.clauses and request.clauses[0].evidence_candidates
        else "default"
    )

    finding = AnalysisProviderFinding(
        finding_id=result.finding_id or f"{result.reference_id}-finding",
        category=result.category,
        risk_type=result.risk_type,
        severity=result.severity,
        title=result.title,
        summary=result.summary,
        risk_reason=result.risk_reason,
        practical_impact=result.practical_impact,
        action_priority=result.action_priority,
        selected_evidence_candidate_ids=[candidate_id],
        questions_to_ask=[
            AnalysisProviderQuestion(
                question_id=str(item.get("question_id", "")),
                question=str(item.get("question", "")),
                purpose=str(item.get("purpose", "")),
                related_evidence_candidate_ids=[
                    str(candidate)
                    for candidate in item.get("related_evidence_ids", [])
                    if isinstance(candidate, str)
                ],
                priority=str(item.get("priority", "normal")),
            )
            for item in result.questions_to_ask
            if isinstance(item, dict)
        ],
        negotiation_suggestions=[
            AnalysisProviderSuggestion(
                suggestion_id=str(item.get("suggestion_id", "")),
                objective=str(item.get("objective", "")),
                suggested_change=str(item.get("suggested_change", "")),
                fallback_option=str(item.get("fallback_option", "")),
                related_evidence_candidate_ids=[
                    str(candidate)
                    for candidate in item.get("related_evidence_ids", [])
                    if isinstance(candidate, str)
                ],
                priority=str(item.get("priority", "normal")),
            )
            for item in result.negotiation_suggestions
            if isinstance(item, dict)
        ],
        recommendation=result.recommendation,
        expert_review_recommended=bool(result.expert_review_recommended),
        expert_review_reason_codes=result.expert_review_reason_codes,
        expert_review_summary=result.expert_review_summary,
        confidence_score=result.confidence_score,
        extracted_fact_candidates=result.extracted_facts,
    )

    response = AnalysisProviderResponse(
        schema_version="analysis-provider-response.v1",
        provider_request_id=request.request_id,
        findings=[finding],
        usage=AnalysisProviderUsage(),
    )
    return response


def _build_retry_exhausted_error(
    *,
    request: AnalysisProviderRequest | None,
    last_error: ProviderExecutionError,
    attempts: int,
) -> ProviderRetryExhausted:
    return ProviderRetryExhausted(
        message="Provider retry attempts exhausted.",
        attempts=attempts,
        request_id=getattr(request, "request_id", None),
        last_reason_code=last_error.reason_code,
    )


def execute_provider(
    provider: AnalysisProvider,
    provider_input: AnalysisProviderInput,
    request: AnalysisProviderRequest | None = None,
    *,
    policy: ProviderExecutionPolicy = DEFAULT_PROVIDER_EXECUTION_POLICY,
    sleep: Callable[[float], None] = time.sleep,
) -> AnalysisProviderResponse | AnalysisResultData:
    policy.validate()

    last_error: ProviderExecutionError | None = None

    for attempt_number in range(1, policy.max_attempts + 1):
        if attempt_number > 1:
            sleep(policy.delay_before_attempt(attempt_number))

        try:
            if request is not None and hasattr(provider, "analyze"):
                request.validate()
                request_payload = request_to_json_bytes(request)
                if len(request_payload) > ANALYSIS_PROVIDER_MAX_REQUEST_BYTES:
                    raise ProviderExecutionError(
                        ProviderFailureReason.PROVIDER_REQUEST_TOO_LARGE,
                        retryable=False,
                        message="Provider request payload exceeded limit.",
                        attempt_number=attempt_number,
                        request_id=request.request_id,
                        raw_payload=request_payload[:1024],
                    )

                raw = provider.analyze(request)  # type: ignore[union-attr]
                if isinstance(raw, AnalysisProviderResponse):
                    raw.validate(request)
                    response_payload = response_to_json_bytes(raw)
                    if len(response_payload) > ANALYSIS_PROVIDER_MAX_RESPONSE_BYTES:
                        raise ProviderExecutionError(
                            ProviderFailureReason.PROVIDER_RESPONSE_TOO_LARGE,
                            retryable=False,
                            message="Provider response payload exceeded limit.",
                            attempt_number=attempt_number,
                            request_id=request.request_id,
                            raw_payload=response_payload[:1024],
                        )
                    return raw
                if isinstance(raw, AnalysisResultData):
                    raw.validate()
                    return _legacy_result_to_provider_response(request, raw)
                raise ProviderInvalidResponseError()

            if hasattr(provider, "analyze_clause"):
                raw = provider.analyze_clause(provider_input)  # type: ignore[union-attr]
                if isinstance(raw, AnalysisResultData):
                    raw.validate()
                    return raw
                raise ProviderInvalidResponseError()

            raise ProviderExecutionError(
                ProviderFailureReason.UNKNOWN,
                retryable=False,
                message="Provider execution failed: missing provider interface.",
                attempt_number=attempt_number,
                request_id=getattr(request, "request_id", None),
            )

        except Exception as exc:  # noqa: PERF203
            if isinstance(exc, ProviderExecutionError):
                execution_error = exc
            elif isinstance(exc, (ValueError, RuntimeError)):
                raise
            else:
                execution_error = _coerce_provider_error(exc)

            last_error = execution_error
            if isinstance(execution_error, ProviderExecutionError):
                execution_error.attempt_number = attempt_number
                if request is not None and execution_error.request_id is None:
                    execution_error.request_id = request.request_id

            if not execution_error.retryable or attempt_number == policy.max_attempts:
                raise execution_error
            continue

    if last_error is not None:
        raise _build_retry_exhausted_error(
            request=request,
            last_error=last_error,
            attempts=policy.max_attempts,
        )

    raise _build_retry_exhausted_error(request=request, last_error=ProviderExecutionError(
        ProviderFailureReason.PROVIDER_RETRY_EXHAUSTED,
        retryable=False,
    ), attempts=policy.max_attempts)
