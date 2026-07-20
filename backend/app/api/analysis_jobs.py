from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.database import get_db
from backend.app.db.models import AnalysisJob, Clause, Document, Extraction
from backend.app.services.analysis_pipeline import run_analysis_pipeline


router = APIRouter(tags=["analysis-jobs"])


def _parse_if_match_version(if_match: str | None) -> int:
    if if_match is None:
        raise HTTPException(
            status_code=400,
            detail="If-Match header is required.",
        )

    version_token = if_match.strip()
    if version_token.startswith("W/"):
        version_token = version_token[2:]
    if version_token.startswith('"') and version_token.endswith('"'):
        version_token = version_token[1:-1]
    try:
        return int(version_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="The If-Match value is invalid.",
        ) from exc


def _snapshot_checksum(items: list[dict[str, object]]) -> str:
    hasher = sha256()
    for item in items:
        hasher.update(str(item["final_text"]).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _get_extraction_ready_for_analysis(
    extraction_id: str,
    db: Session,
    *,
    if_match: str | None,
) -> Extraction:
    statement = (
        select(Extraction)
        .options(selectinload(Extraction.pages))
        .where(Extraction.id == extraction_id)
    )
    extraction = db.scalar(statement)

    if extraction is None:
        raise HTTPException(
            status_code=404,
            detail="Extraction not found.",
        )

    request_version = _parse_if_match_version(if_match)

    extra_data = extraction.extra_data or {}

    if extraction.status != "confirmed":
        raise HTTPException(
            status_code=409,
            detail="confirmation_required",
        )

    if (extra_data.get("review_status") or "").lower() != "confirmed":
        raise HTTPException(
            status_code=409,
            detail="confirmation_required",
        )

    try:
        snapshot_version = int(extra_data.get("snapshot_version", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail="The extraction snapshot revision is unavailable.",
        ) from exc

    if request_version != snapshot_version:
        raise HTTPException(
            status_code=409,
            detail="extraction revision mismatch",
        )

    snapshot = extra_data.get("confirmation_snapshot")
    if not isinstance(snapshot, list) or not snapshot:
        raise HTTPException(
            status_code=409,
            detail="confirmation_required",
        )

    page_numbers: list[int] = []
    page_ids: list[str] = []
    for item in snapshot:
        page_number = item.get("page_number")
        page_id = item.get("page_id")
        final_text = item.get("final_text")

        if not isinstance(page_number, int) or page_number < 1:
            raise HTTPException(
                status_code=409,
                detail="extraction_review_incomplete",
            )
        if not isinstance(page_id, str) or not page_id.strip():
            raise HTTPException(
                status_code=409,
                detail="extraction_review_incomplete",
            )
        if not isinstance(final_text, str) or not final_text.strip():
            raise HTTPException(
                status_code=409,
                detail="invalid_confirmation_snapshot",
            )

        page_numbers.append(page_number)
        page_ids.append(page_id)

    if sorted(page_numbers) != list(range(1, len(page_numbers) + 1)):
        raise HTTPException(
            status_code=409,
            detail="extraction_review_incomplete",
        )
    if len(set(page_ids)) != len(page_ids):
        raise HTTPException(
            status_code=409,
            detail="extraction_review_incomplete",
        )

    expected_checksum = _snapshot_checksum(snapshot)
    stored_checksum = extra_data.get("confirmation_checksum")
    if stored_checksum != expected_checksum:
        raise HTTPException(
            status_code=409,
            detail="stale_extraction_revision",
        )

    return extraction


def _load_or_create_analysis_document(
    db: Session,
    extraction: Extraction,
) -> str:
    statement = select(Document).where(Document.id == extraction.id)
    document = db.scalar(statement)
    extraction_data = extraction.extra_data or {}
    snapshot = extraction_data["confirmation_snapshot"]

    if document is None:
        document = Document(
            id=extraction.id,
            filename=extraction.filename_display,
            content_type=extraction.source_type,
            size_bytes=extraction.size_bytes,
            character_count=int(extraction_data.get("final_total_text_length", 0)),
            status="processed",
            unclassified_sections=[],
            document_warnings=extraction.warnings,
        )
        db.add(document)
        db.flush()

        for position, page_data in enumerate(snapshot, start=1):
            body = str(page_data["final_text"])
            clause = Clause(
                id=str(uuid4()),
                clause_id=f"page-{position}",
                reference_id=f"{document.id}:clause:{position}",
                source_hash=str(sha256(body.encode("utf-8")).hexdigest()),
                ordinal=position,
                marker="page",
                clause_type="page",
                title=f"Page {page_data['page_number']}",
                body=body,
                warnings=list(page_data.get("warnings") or []),
            )
            document.clauses.append(clause)
        db.flush()

        return document.id

    if not document.clauses:
        for position, page_data in enumerate(snapshot, start=1):
            body = str(page_data["final_text"])
            clause = Clause(
                id=str(uuid4()),
                clause_id=f"page-{position}",
                reference_id=f"{document.id}:clause:{position}",
                source_hash=str(sha256(body.encode("utf-8")).hexdigest()),
                ordinal=position,
                marker="page",
                clause_type="page",
                title=f"Page {page_data['page_number']}",
                body=body,
                warnings=list(page_data.get("warnings") or []),
            )
            document.clauses.append(clause)
        db.flush()

    return document.id


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
        status="queued",
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    run_analysis_pipeline(
        db=db,
        job=job,
        clauses=sorted(
            document.clauses,
            key=lambda clause: clause.ordinal,
        ),
    )

    return {
        "job_id": job.id,
        "document_id": job.document_id,
        "status": job.status,
    }


@router.post("/extractions/{extraction_id}/analysis-jobs")
def create_extraction_analysis_job(
    extraction_id: str,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    extraction = _get_extraction_ready_for_analysis(
        extraction_id,
        db,
        if_match=if_match,
    )

    document_id = _load_or_create_analysis_document(db, extraction)
    statement = (
        select(Clause)
        .where(Clause.reference_id.like(f"{document_id}:clause:%"))
        .order_by(Clause.ordinal)
    )
    clauses = db.scalars(statement).all()

    if not clauses:
        raise HTTPException(
            status_code=409,
            detail="stale_extraction_revision",
        )

    job = AnalysisJob(
        id=str(uuid4()),
        document_id=document_id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    run_analysis_pipeline(
        db=db,
        job=job,
        clauses=clauses,
    )

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
