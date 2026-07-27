from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.models import AnalysisJob, Document
from backend.app.services.analysis_job_queue import claim_next_job, finish_job_success
from backend.app.services.analysis_pipeline import run_analysis_pipeline
from backend.app.services.analysis_provider import AnalysisProvider
from backend.app.services.analysis_provider_factory import create_analysis_provider


def run_pending_job(
    db: Session,
    job_id: str,
    *,
    provider: AnalysisProvider | None = None,
) -> AnalysisJob:
    claimed = claim_next_job(
        db,
        worker_id="pytest-analysis-worker",
        lease_seconds=120,
    )
    if claimed is None or claimed.id != job_id:
        raise AssertionError("Expected pending analysis job was not claimed.")
    job = db.scalar(
        select(AnalysisJob)
        .options(
            selectinload(AnalysisJob.document).selectinload(Document.clauses)
        )
        .where(AnalysisJob.id == job_id)
    )
    if job is None:
        raise AssertionError("Claimed analysis job is unavailable.")
    run_analysis_pipeline(
        db=db,
        job=job,
        clauses=sorted(job.document.clauses, key=lambda clause: clause.ordinal),
        provider=provider or create_analysis_provider(),
        worker_managed=True,
    )
    finish_job_success(db, job=job, worker_id="pytest-analysis-worker")
    db.refresh(job)
    return job
