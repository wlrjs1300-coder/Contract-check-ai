from uuid import uuid4

from backend.app.db.models import Clause
from backend.app.services.analysis_provider import (
    SyntheticAnalysisProvider,
)


def test_synthetic_provider_returns_expected_result() -> None:
    clause = Clause(
        id=str(uuid4()),
        clause_id="clause-001",
        reference_id="document-id:clause:1",
        source_hash="test-source-hash",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title=None,
        body="Synthetic clause body.",
        warnings=[],
    )

    provider = SyntheticAnalysisProvider()

    result = provider.analyze_clause(clause)

    assert result.reference_id == clause.reference_id
    assert result.display_label == "추가 확인"
    assert result.summary == "합성 분석 결과입니다."
    assert result.expert_review_recommended is False

    result.validate()
