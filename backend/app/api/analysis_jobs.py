from uuid import uuid4

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["analysis-jobs"])

analysis_jobs: dict[str, dict[str, str]] = {}


@router.post("/documents/{document_id}/analysis-jobs")
def create_analysis_job(document_id: str) -> dict[str, str]:
    job_id = str(uuid4())

    job = {
        "job_id": job_id,
        "document_id": document_id,
        "status": "queued",
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
