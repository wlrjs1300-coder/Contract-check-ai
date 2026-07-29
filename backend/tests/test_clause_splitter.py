from pathlib import Path

from backend.app.services.clause_splitter import split_clauses


FIXTURE_PATH = Path(
    "backend/tests/fixtures/clause-split-smoke.sample.txt"
)


def test_split_clauses_from_synthetic_employment_contract() -> None:
    text = FIXTURE_PATH.read_text(encoding="utf-8-sig")

    result = split_clauses(text, "doc-test")

    assert result["clause_count"] == 2

    clauses = result["clauses"]
    assert clauses[0]["clause_id"] == "clause-001"
    assert clauses[0]["title"] == "목적"
    assert clauses[0]["body"] == "근로조건을 정한다."

    assert clauses[1]["clause_id"] == "clause-002"
    assert clauses[1]["title"] == "기간"
    assert clauses[1]["body"] == "계약기간은 1년이다."

    assert result["document_warnings"] == []
