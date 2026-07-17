from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from backend.app.services.analysis_provider import (
    AnalysisProvider,
    AnalysisProviderInput,
)
from backend.app.services.analysis_result_schema import AnalysisResultData


class ProviderFailureReason(StrEnum):
    TIMEOUT = "PROVIDER_TIMEOUT"
    TRANSPORT_ERROR = "PROVIDER_TRANSPORT_ERROR"
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    AUTHENTICATION_ERROR = "PROVIDER_AUTHENTICATION_ERROR"
    NOT_APPROVED = "PROVIDER_NOT_APPROVED"
    EXECUTION_FAILED = "PROVIDER_EXECUTION_FAILED"


class ProviderExecutionError(RuntimeError):
    def __init__(
        self,
        reason_code: ProviderFailureReason,
        *,
        retryable: bool,
    ) -> None:
        super().__init__("Provider execution failed.")
        self.reason_code = reason_code
        self.retryable = retryable


class ProviderTimeoutError(ProviderExecutionError):
    def __init__(self) -> None:
        super().__init__(
            ProviderFailureReason.TIMEOUT,
            retryable=True,
        )


class ProviderTransportError(ProviderExecutionError):
    def __init__(self) -> None:
        super().__init__(
            ProviderFailureReason.TRANSPORT_ERROR,
            retryable=True,
        )


class ProviderRateLimitError(ProviderExecutionError):
    def __init__(self) -> None:
        super().__init__(
            ProviderFailureReason.RATE_LIMITED,
            retryable=True,
        )


class ProviderAuthenticationError(ProviderExecutionError):
    def __init__(self) -> None:
        super().__init__(
            ProviderFailureReason.AUTHENTICATION_ERROR,
            retryable=False,
        )


class ProviderNotApprovedError(ProviderExecutionError):
    def __init__(self) -> None:
        super().__init__(
            ProviderFailureReason.NOT_APPROVED,
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
            raise ValueError(
                "backoff_seconds must not contain negative values."
            )

    def delay_before_attempt(self, attempt_number: int) -> float:
        delay_index = attempt_number - 2

        if delay_index < 0:
            return 0.0

        if delay_index >= len(self.backoff_seconds):
            return 0.0

        return self.backoff_seconds[delay_index]


DEFAULT_PROVIDER_EXECUTION_POLICY = ProviderExecutionPolicy()


def execute_provider(
    provider: AnalysisProvider,
    provider_input: AnalysisProviderInput,
    *,
    policy: ProviderExecutionPolicy = DEFAULT_PROVIDER_EXECUTION_POLICY,
    sleep: Callable[[float], None] = lambda _seconds: None,
) -> AnalysisResultData:
    policy.validate()

    for attempt_number in range(1, policy.max_attempts + 1):
        if attempt_number > 1:
            sleep(policy.delay_before_attempt(attempt_number))

        try:
            return provider.analyze_clause(provider_input)
        except ProviderExecutionError as exc:
            if not exc.retryable:
                raise

            if attempt_number == policy.max_attempts:
                raise

    raise ProviderExecutionError(
        ProviderFailureReason.EXECUTION_FAILED,
        retryable=False,
    )
