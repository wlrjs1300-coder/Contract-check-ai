from typing import Protocol

from backend.app.db.models import Clause
from backend.app.services.analysis_result_schema import AnalysisResultData


class AnalysisProvider(Protocol):
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        ...


class SyntheticAnalysisProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id=clause.reference_id,
            display_label="추가 확인",
            summary="합성 분석 결과입니다.",
            expert_review_recommended=False,
        )


DEFAULT_ANALYSIS_PROVIDER: AnalysisProvider = SyntheticAnalysisProvider()