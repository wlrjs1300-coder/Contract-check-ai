from __future__ import annotations

import pytest

from backend.app.services.analysis_provider import AnalysisProviderInput
from backend.app.services.analysis_provider_contract import (
    AnalysisClauseInput,
    AnalysisProviderRequest,
    EvidenceCandidateInput,
)
from backend.app.services.fake_analysis_provider import FakeAnalysisProvider
from backend.app.services.provider_execution import (
    ProviderExecutionError,
    ProviderFailureReason,
    ProviderExecutionPolicy,
    execute_provider,
)


def _request() -> AnalysisProviderRequest:
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
                evidence_candidates=[
                    EvidenceCandidateInput(
                        candidate_id="doc-1:clause:1-e001",
                        clause_id="doc-1:clause:1",
                        page_number=1,
                        block_ids=["b1"],
                    )
                ],
            )
        ],
    )


def _provider_input() -> AnalysisProviderInput:
    return AnalysisProviderInput(reference_id="doc-1:clause:1", masked_text="contract")


def test_execute_provider_timeout_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ANALYSIS_PROVIDER_MODE", "timeout")
    provider = FakeAnalysisProvider()

    with pytest.raises(ProviderExecutionError) as exc_info:
        execute_provider(
            provider,
            _provider_input(),
            request=_request(),
            policy=ProviderExecutionPolicy(max_attempts=2, backoff_seconds=(0.0,)),
            sleep=lambda x: None,
        )

    assert exc_info.value.reason_code == ProviderFailureReason.PROVIDER_TIMEOUT
    assert exc_info.value.retryable is False or exc_info.value.attempt_number == 2


def test_execute_provider_rate_limit_retries_to_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_ANALYSIS_PROVIDER_MODE", "rate_limit")
    provider = FakeAnalysisProvider()

    with pytest.raises(ProviderExecutionError) as exc_info:
        execute_provider(
            provider,
            _provider_input(),
            request=_request(),
            policy=ProviderExecutionPolicy(max_attempts=3, backoff_seconds=(0.0, 0.0)),
            sleep=lambda x: None,
        )

    assert exc_info.value.reason_code == ProviderFailureReason.PROVIDER_RATE_LIMITED
    assert exc_info.value.attempt_number == 3


def test_execute_provider_request_id_and_payload_limit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ANALYSIS_PROVIDER_MODE", "oversized_response")
    provider = FakeAnalysisProvider()

    with pytest.raises(ProviderExecutionError) as exc_info:
        execute_provider(
            provider,
            _provider_input(),
            request=_request(),
            policy=ProviderExecutionPolicy(max_attempts=1),
        )

    assert exc_info.value.reason_code == ProviderFailureReason.PROVIDER_RESPONSE_TOO_LARGE


def test_execute_provider_success_with_fake() -> None:
    request = _request()
    provider = FakeAnalysisProvider()
    result = execute_provider(
        provider,
        _provider_input(),
        request=request,
        policy=ProviderExecutionPolicy(max_attempts=1),
    )

    assert result is not None
