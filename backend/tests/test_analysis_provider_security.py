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
        request_id="req-secure",
        document_id="doc-secure",
        snapshot_version=1,
        clauses=[
            AnalysisClauseInput(
                clause_id="doc-secure:clause:1",
                clause_label="제1조",
                clause_level="normal",
                text="계약 내용",
                evidence_candidates=[
                    EvidenceCandidateInput(
                        candidate_id="doc-secure:clause:1-e001",
                        clause_id="doc-secure:clause:1",
                        page_number=1,
                        block_ids=["b1"],
                        source_text="SECRET_TOKEN=abc123",
                    )
                ],
            )
        ],
    )


def _provider_input() -> AnalysisProviderInput:
    return AnalysisProviderInput(reference_id="doc-secure:clause:1", masked_text="contract")


def test_provider_error_does_not_expose_raw_payload_in_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_ANALYSIS_PROVIDER_MODE", "temporary_failure")

    with pytest.raises(ProviderExecutionError) as exc_info:
        execute_provider(
            FakeAnalysisProvider(),
            _provider_input(),
            request=_request(),
            policy=ProviderExecutionPolicy(max_attempts=1),
        )

    assert exc_info.value.reason_code == ProviderFailureReason.PROVIDER_TEMPORARY_FAILURE
    assert "SECRET_TOKEN" not in str(exc_info.value)
    assert "doc-secure" not in str(exc_info.value)


def test_request_context_is_kept_for_debug() -> None:
    error = ProviderExecutionError(
        ProviderFailureReason.PROVIDER_TEMPORARY_FAILURE,
        retryable=True,
        message="temporary fail",
        attempt_number=2,
        request_id="req-secure",
    )
    assert error.attempt_number == 2
    assert error.request_id == "req-secure"
