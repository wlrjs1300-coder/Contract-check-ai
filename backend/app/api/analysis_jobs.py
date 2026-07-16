from uuid import uuid4

from fastapi import APIRouter, HTTPException

from backend.app.services.analysis_result_store import analysis_results
from backend.app.services.document_store import documents

router = APIRouter(tags=["analysis-jobs"])

analysis_jobs: dict[str, dict[str, str]] = {}


@router.post("/documents/{document_id}/analysis-jobs")
def create_analysis_job(document_id: str) -> dict[str, str]:
    document = documents.get(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    job_id = str(uuid4())

    job = {
        "job_id": job_id,
        "document_id": document_id,
        "status": "completed",
    }

    clauses = document["clauses"]

    analysis_results[document_id] = {
        "document_id": document_id,
        "job_id": job_id,
        "status": "completed",
        "items": [
            {
                "clause_id": clause["clause_id"],
                "reference_id": clause["reference_id"],
                "display_label": "추가 확인",
                "summary": "합성 분석 결과입니다.",
                "expert_review_recommended": False,
            }
            for clause in clauses
        ],
    }

    analysis_jobs[job_id] = job
    return job


@router.get("/analysis-jobs/{job_id}")
def get_analysis_job(job_id: str) -> dict[str, str]:
    job = analysis_jobs.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis job not found.",
        )

    return job
