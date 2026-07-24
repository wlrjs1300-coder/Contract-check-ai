import pytest

from uuid import uuid4

from backend.app.db.models import AnalysisJob, Clause, Document, Extraction
from backend.app.services.analysis_pipeline import run_analysis_pipeline
from backend.app.services.evidence_linking import calculate_snapshot_hash
from backend.app.services.scalar_encryption import encrypt_clause_body
from backend.app.core.encryption_config import get_encryption_keyring
from backend.tests.support import TEST_USER_ID


def _fake_document_and_clause(session, document_id: str, body: str) -> tuple[Document, Clause]:
    clause_id = str(uuid4())
    keyring = get_encryption_keyring()
    document = Document(
        id=document_id,
        owner_id=TEST_USER_ID,
        filename="flow.txt",
        content_type="text/plain",
        size_bytes=len(body),
        character_count=len(body),
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )
    clause = Clause(
        id=clause_id,
        clause_id="snapshot-clause-001",
        reference_id=f"{document_id}:clause:1",
        source_hash="fake",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title="목적",
        body_encrypted=encrypt_clause_body(
            body,
            clause_id=clause_id,
            owner_id=TEST_USER_ID,
            keyring=keyring,
        ),
        warnings=[],
    )
    clause.start_offset = 0
    clause.end_offset = len(body)
    clause.page_start = 1
    clause.page_end = 1
    clause.block_ids = ["p1-b1"]
    document.clauses.append(clause)
    session.add(document)
    session.commit()
    session.refresh(document)
    session.refresh(clause)
    return document, clause


def test_analysis_job_fails_when_evidence_does_not_match_snapshot(db_session):
    document_id = str(uuid4())
    body = "계약의 목적은 테스트 목적입니다."
    document, clause = _fake_document_and_clause(db_session, document_id, body)

    extraction = Extraction(
        id=document_id,
        owner_id=TEST_USER_ID,
        filename_display="flow.pdf",
        source_type="pdf",
        size_bytes=10,
        page_count=1,
        status="confirmed",
        method="ocr",
        warnings=[],
        requires_user_review=False,
        extra_data={
            "confirmation_snapshot": [
                {
                    "page_number": 1,
                    "final_text": "전혀 다른 텍스트입니다.",
                    "blocks": [
                        {
                            "block_id": "p1-b1",
                            "text": "전혀 다른 텍스트입니다.",
                            "start_in_page_offset": 0,
                            "end_in_page_offset": 11,
                        }
                    ],
                }
            ],
            "confirmation_checksum": calculate_snapshot_hash([
                {"page_number": 1, "final_text": "전혀 다른 텍스트입니다.", "blocks": []}
            ]),
            "snapshot_version": 1,
        },
    )
    db_session.add(extraction)
    db_session.commit()

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document_id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError, match="evidence"):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
        )
