from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.database import get_db
from backend.app.db.models import (
    AnalysisJob,
    AnalysisResultItem,
    Document,
)


router = APIRouter(tags=["analysis-jobs"])


@router.post("/documents/{document_id}/analysis-jobs")
def create_analysis_job(
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    statement = (
        select(Document)
        .options(selectinload(Document.clauses))
        .where(Document.id == document_id)
    )
    document = db.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document_id,
        status="completed",
    )

    for clause in document.clauses:
        job.result_items.append(
            AnalysisResultItem(
                clause_record_id=clause.id,
                reference_id=clause.reference_id,
                display_label="추가 확인",
                summary="합성 분석 결과입니다.",
                expert_review_recommended=False,
                extra_data={},
            )
        )

    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "job_id": job.id,
        "document_id": job.document_id,
        "status": job.status,
    }


@router.get("/analysis-jobs/{job_id}")
def get_analysis_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    job = db.get(AnalysisJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis job not found.",
        )

    return {
        "job_id": job.id,
        "document_id": job.document_id,
        "status": job.status,
    }
