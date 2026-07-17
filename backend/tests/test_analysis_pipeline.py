from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.db.models import AnalysisJob, Clause, Document
from backend.app.services.analysis_pipeline import (
    run_analysis_pipeline,
    validate_reference_id,
)
from backend.app.services.analysis_result_schema import AnalysisResultData


def _create_document_and_clause(
    db: Session,
    *,
    reference_id: str | None = None,
) -> tuple[Document, Clause]:
    document_id = str(uuid4())

    document = Document(
        id=document_id,
        filename="pipeline.sample.txt",
        content_type="text/plain",
        size_bytes=10,
        character_count=10,
        status="processed",
        unclassified_sections=[],
        document_warnings=[],
    )

    clause = Clause(
        id=str(uuid4()),
        clause_id="clause-001",
        reference_id=(
            reference_id
            if reference_id is not None
            else f"{document_id}:clause:1"
        ),
        source_hash="test-source-hash",
        ordinal=1,
        marker="1.",
        clause_type="normal",
        title=None,
        body="Synthetic clause body.",
        warnings=[],
    )

    document.clauses.append(clause)
    db.add(document)
    db.commit()
    db.refresh(document)
    db.refresh(clause)

    return document, clause


def test_validate_reference_id_accepts_matching_value(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    validate_reference_id(document.id, clause)


def test_validate_reference_id_rejects_mismatch(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(
        db_session,
        reference_id="invalid-reference-id",
    )

    with pytest.raises(
        ValueError,
        match="Clause reference_id does not match",
    ):
        validate_reference_id(document.id, clause)


def test_run_analysis_pipeline_completes_job(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    run_analysis_pipeline(db_session, job, [clause])

    assert job.status == "completed"
    assert len(job.result_items) == 1
    assert job.result_items[0].reference_id == clause.reference_id
    assert (
        job.result_items[0].display_label
        == "\ucd94\uac00 \ud655\uc778"
    )


def test_run_analysis_pipeline_marks_job_failed(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(
        db_session,
        reference_id="invalid-reference-id",
    )

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError):
        run_analysis_pipeline(db_session, job, [clause])

    db_session.refresh(job)

    assert job.status == "failed"
    assert job.result_items == []



def test_run_analysis_pipeline_rolls_back_partial_results(
    db_session: Session,
) -> None:
    document, first_clause = _create_document_and_clause(db_session)

    second_clause = Clause(
        id=str(uuid4()),
        clause_id="clause-002",
        reference_id="invalid-reference-id",
        source_hash="second-source-hash",
        ordinal=2,
        marker="2.",
        clause_type="normal",
        title=None,
        body="Second synthetic clause body.",
        warnings=[],
        document_id=document.id,
    )
    db_session.add(second_clause)
    db_session.commit()
    db_session.refresh(second_clause)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(ValueError):
        run_analysis_pipeline(
            db_session,
            job,
            [first_clause, second_clause],
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


class CustomAnalysisProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id=clause.reference_id,
            display_label="주의",
            summary="교체된 provider 결과입니다.",
            expert_review_recommended=True,
        )


class InvalidAnalysisProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        return AnalysisResultData(
            reference_id=clause.reference_id,
            display_label="허용되지 않은 라벨",
            summary="잘못된 provider 결과입니다.",
            expert_review_recommended=False,
        )


class FailingAnalysisProvider:
    def analyze_clause(
        self,
        clause: Clause,
    ) -> AnalysisResultData:
        raise RuntimeError("Synthetic provider failure.")


def test_run_analysis_pipeline_accepts_custom_provider(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    run_analysis_pipeline(
        db_session,
        job,
        [clause],
        provider=CustomAnalysisProvider(),
    )

    assert job.status == "completed"
    assert len(job.result_items) == 1
    assert job.result_items[0].display_label == "주의"
    assert (
        job.result_items[0].summary
        == "교체된 provider 결과입니다."
    )
    assert job.result_items[0].expert_review_recommended is True


def test_run_analysis_pipeline_rejects_invalid_provider_result(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        ValueError,
        match="display_label must be one of the allowed labels",
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=InvalidAnalysisProvider(),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []


def test_run_analysis_pipeline_handles_provider_failure(
    db_session: Session,
) -> None:
    document, clause = _create_document_and_clause(db_session)

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document.id,
        status="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    with pytest.raises(
        RuntimeError,
        match="Synthetic provider failure",
    ):
        run_analysis_pipeline(
            db_session,
            job,
            [clause],
            provider=FailingAnalysisProvider(),
        )

    failed_job = db_session.get(AnalysisJob, job.id)

    assert failed_job is not None
    assert failed_job.status == "failed"
    assert failed_job.result_items == []
