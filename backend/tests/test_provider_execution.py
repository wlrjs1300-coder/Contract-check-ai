import pytest

from backend.app.services.analysis_provider import (
    AnalysisProviderInput,
)
from backend.app.services.analysis_result_schema import AnalysisResultData
from backend.app.services.provider_execution import (
    ProviderAuthenticationError,
    ProviderExecutionPolicy,
    ProviderFailureReason,
    ProviderRateLimitError,
    ProviderTimeoutError,
    execute_provider,
)


class EventuallySuccessfulProvider:
    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.call_count += 1

        if self.call_count <= self.failures_before_success:
            raise ProviderTimeoutError()

        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary="합성 분석 결과입니다.",
            expert_review_recommended=False,
        )


class AlwaysRateLimitedProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.call_count += 1
        raise ProviderRateLimitError()


class AuthenticationFailureProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        self.call_count += 1
        raise ProviderAuthenticationError()


def _provider_input() -> AnalysisProviderInput:
    return AnalysisProviderInput(
        reference_id="document-id:clause:1",
        masked_text="Synthetic masked clause.",
    )


def test_execute_provider_retries_then_succeeds() -> None:
    provider = EventuallySuccessfulProvider(
        failures_before_success=2,
    )
    delays: list[float] = []

    result = execute_provider(
        provider,
        _provider_input(),
        policy=ProviderExecutionPolicy(
            max_attempts=3,
            backoff_seconds=(0.1, 0.2),
        ),
        sleep=delays.append,
    )

    assert provider.call_count == 3
    assert delays == [0.1, 0.2]
    assert result.reference_id == "document-id:clause:1"


def test_execute_provider_raises_after_retry_exhaustion() -> None:
    provider = AlwaysRateLimitedProvider()
    delays: list[float] = []

    with pytest.raises(ProviderRateLimitError) as exc_info:
        execute_provider(
            provider,
            _provider_input(),
            policy=ProviderExecutionPolicy(
                max_attempts=3,
                backoff_seconds=(0.5, 1.0),
            ),
            sleep=delays.append,
        )

    assert provider.call_count == 3
    assert delays == [0.5, 1.0]
    assert (
        exc_info.value.reason_code
        == ProviderFailureReason.RATE_LIMITED
    )
    assert exc_info.value.retryable is True
    assert str(exc_info.value) == "Provider execution failed."


def test_execute_provider_does_not_retry_non_retryable_error() -> None:
    provider = AuthenticationFailureProvider()
    delays: list[float] = []

    with pytest.raises(ProviderAuthenticationError) as exc_info:
        execute_provider(
            provider,
            _provider_input(),
            policy=ProviderExecutionPolicy(
                max_attempts=3,
                backoff_seconds=(0.5, 1.0),
            ),
            sleep=delays.append,
        )

    assert provider.call_count == 1
    assert delays == []
    assert (
        exc_info.value.reason_code
        == ProviderFailureReason.AUTHENTICATION_ERROR
    )
    assert exc_info.value.retryable is False


@pytest.mark.parametrize(
    "policy",
    [
        ProviderExecutionPolicy(max_attempts=0),
        ProviderExecutionPolicy(
            max_attempts=2,
            backoff_seconds=(-1.0,),
        ),
    ],
)
def test_provider_execution_policy_rejects_invalid_values(
    policy: ProviderExecutionPolicy,
) -> None:
    with pytest.raises(ValueError):
        policy.validate()
