import pytest

from backend.app.services.evidence_linking import (
    EvidenceValidationError,
    bind_evidence_to_finding,
    build_evidence_candidates,
    calculate_snapshot_hash,
    validate_evidence_reference,
    validate_finding_evidence,
)


def _fixture_snapshot() -> list[dict[str, object]]:
    return [
        {
            "page_number": 1,
            "final_text": "제1조(목적)\n이 계약의 목적은 테스트입니다.\n",
            "blocks": [
                {
                    "block_id": "p1-b1",
                    "text": "제1조(목적)",
                    "start_in_page_offset": 0,
                    "end_in_page_offset": 8,
                },
                {
                    "block_id": "p1-b2",
                    "text": "이 계약의 목적은 테스트입니다.",
                    "start_in_page_offset": 8,
                    "end_in_page_offset": 27,
                },
            ],
        }
    ]


def test_build_evidence_candidates_rejects_no_match() -> None:
    snapshot = _fixture_snapshot()
    evidence = build_evidence_candidates(
            document_id="doc",
            extraction_id="ext",
            clause_id="doc:clause:1",
            source_text="없는문구",
            snapshot=snapshot,
            snapshot_hash=calculate_snapshot_hash(snapshot),
        )
    assert evidence == []
    with pytest.raises(EvidenceValidationError, match="No evidence"):
        validate_finding_evidence(
            evidence_list=evidence,
            snapshot=snapshot,
            document_id="doc",
            extraction_id="ext",
            clause_id="doc:clause:1",
            snapshot_hash=calculate_snapshot_hash(snapshot),
        )


def test_resolve_exact_and_normalized_match() -> None:
    snapshot = _fixture_snapshot()
    evidence = build_evidence_candidates(
        document_id="doc",
        extraction_id="ext",
        clause_id="doc:clause:1",
        source_text="이 계약의 목적은 테스트입니다.\r\n",
        snapshot=snapshot,
        snapshot_hash=calculate_snapshot_hash(snapshot),
    )
    assert len(evidence) == 1


def test_validate_evidence_wrong_document_and_page() -> None:
    snapshot = _fixture_snapshot()
    evidence = {
        "evidence_id": "doc:clause:1-e001",
        "document_id": "doc-wrong",
        "extraction_id": "ext",
        "page_number": 1,
        "clause_id": "doc:clause:1",
        "source_text": "이 계약의 목적은 테스트입니다.",
        "start_offset": 10,
        "end_offset": 20,
        "block_ids": ["p1-b2"],
        "validation_status": "exact_match",
        "evidence_snapshot_hash": calculate_snapshot_hash(snapshot),
    }
    with pytest.raises(EvidenceValidationError, match="document_id"):
        validate_evidence_reference(
            evidence=evidence,
            snapshot_pages={1: snapshot[0]},
            document_id="doc",
            extraction_id="ext",
            snapshot_hash=calculate_snapshot_hash(snapshot),
            clause_id="doc:clause:1",
        )


def test_validate_evidence_rejects_missing_blocks() -> None:
    snapshot = _fixture_snapshot()
    evidence = {
        "evidence_id": "doc:clause:1-e001",
        "document_id": "doc",
        "extraction_id": "ext",
        "page_number": 1,
        "clause_id": "doc:clause:1",
        "source_text": "이 계약의 목적은 테스트입니다.",
        "start_offset": 9,
        "end_offset": 17,
        "block_ids": [],
        "validation_status": "exact_match",
        "evidence_snapshot_hash": calculate_snapshot_hash(snapshot),
    }
    with pytest.raises(EvidenceValidationError, match="block_ids"):
        validate_evidence_reference(
            evidence=evidence,
            snapshot_pages={1: snapshot[0]},
            document_id="doc",
            extraction_id="ext",
            snapshot_hash=calculate_snapshot_hash(snapshot),
            clause_id="doc:clause:1",
        )


def test_binds_and_validates_simple_clause() -> None:
    class Clause:
        reference_id = "doc:clause:1"
        body = "이 계약의 목적은 테스트입니다."

    snapshot = _fixture_snapshot()
    evidence = bind_evidence_to_finding(
        document_id="doc",
        extraction_id="ext",
        clause=Clause(),
        snapshot=snapshot,
        snapshot_hash=calculate_snapshot_hash(snapshot),
        snapshot_version=1,
    )
    assert evidence
