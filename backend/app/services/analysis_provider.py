from dataclasses import dataclass
from typing import Protocol

from backend.app.services.analysis_result_schema import AnalysisResultData


@dataclass(frozen=True)
class AnalysisProviderInput:
    reference_id: str
    masked_text: str


class AnalysisProvider(Protocol):
    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        ...


class SyntheticAnalysisProvider:
    def analyze_clause(
        self,
        provider_input: AnalysisProviderInput,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id=provider_input.reference_id,
            display_label="추가 확인",
            summary="합성 분석 결과입니다.",
            expert_review_recommended=False,
        )


DEFAULT_ANALYSIS_PROVIDER: AnalysisProvider = SyntheticAnalysisProvider()
