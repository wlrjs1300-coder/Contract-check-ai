from backend.app.services.clause_splitter import split_clauses_with_snapshot


def test_split_clause_markers_and_fallback() -> None:
    snapshot = [
        {
            "page_number": 1,
            "final_text": "제1조\n계약의 목적은 다음과 같다.\n가. 먼저 한다.\n",
            "blocks": [{"block_id": "", "text": "제1조"}],
        },
        {
            "page_number": 2,
            "final_text": "계속 조항 내용입니다.",
            "blocks": [],
        },
    ]

    result = split_clauses_with_snapshot(snapshot, document_id="doc")
    assert result["clause_count"] >= 1
    first = result["clauses"][0]
    assert first["split_method"] == "marker_split"
    assert first["page_start"] == 1
    assert first["page_end"] >= 1
    assert "block_ids" in first


def test_split_snapshot_fallback_for_unmarked_document() -> None:
    snapshot = [
        {
            "page_number": 1,
            "final_text": "서문 내용만 있고 조항 번호가 없다.\n",
            "blocks": [],
        }
    ]
    result = split_clauses_with_snapshot(snapshot, document_id="doc2")
    clauses = result["clauses"]
    assert len(clauses) == 1
    assert clauses[0]["split_method"] == "whole_document_fallback"
