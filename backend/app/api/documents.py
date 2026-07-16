from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.database import get_db
from backend.app.db.models import (
    AnalysisJob,
    AnalysisResultItem,
    Clause,
    Document,
)
from backend.app.services.clause_splitter import split_clauses


router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 1 * 1024 * 1024
ALLOWED_SUFFIXES = {".txt"}


def _serialize_clause(clause: Clause) -> dict[str, object]:
    return {
        "clause_id": clause.clause_id,
        "reference_id": clause.reference_id,
        "source_hash": clause.source_hash,
        "ordinal": clause.ordinal,
        "marker": clause.marker,
        "clause_type": clause.clause_type,
        "title": clause.title,
        "body": clause.body,
        "warnings": clause.warnings,
    }


def _serialize_document(document: Document) -> dict[str, object]:
    clauses = sorted(document.clauses, key=lambda clause: clause.ordinal)

    return {
        "document_id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "character_count": document.character_count,
        "status": document.status,
        "clause_count": len(clauses),
        "clauses": [_serialize_clause(clause) for clause in clauses],
        "unclassified_sections": document.unclassified_sections,
        "document_warnings": document.document_warnings,
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Only .txt files are allowed.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The uploaded file exceeds the 1 MB limit.",
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file must be UTF-8 encoded.",
        ) from exc

    document_id = str(uuid4())
    clause_result = split_clauses(text, document_id)

    document = Document(
        id=document_id,
        filename=filename,
        content_type=file.content_type,
        size_bytes=len(content),
        character_count=len(text),
        status="processed",
        unclassified_sections=clause_result["unclassified_sections"],
        document_warnings=clause_result["document_warnings"],
    )

    for clause_data in clause_result["clauses"]:
        document.clauses.append(
            Clause(
                id=str(uuid4()),
                clause_id=clause_data["clause_id"],
                reference_id=clause_data["reference_id"],
                source_hash=clause_data["source_hash"],
                ordinal=clause_data["ordinal"],
                marker=clause_data["marker"],
                clause_type=clause_data["clause_type"],
                title=clause_data["title"],
                body=clause_data["body"],
                warnings=clause_data["warnings"],
            )
        )

    db.add(document)
    db.commit()
    db.refresh(document)

    return _serialize_document(document)


@router.get("/{document_id}")
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
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

    return _serialize_document(document)


@router.get("/{document_id}/analysis-results")
def get_analysis_results(
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    statement = (
        select(AnalysisJob)
        .options(
            selectinload(AnalysisJob.result_items).selectinload(
                AnalysisResultItem.clause
            )
        )
        .where(AnalysisJob.document_id == document_id)
        .order_by(AnalysisJob.created_at.desc())
    )
    job = db.scalars(statement).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis result not found.",
        )

    items = sorted(
        job.result_items,
        key=lambda item: item.clause.ordinal,
    )

    return {
        "document_id": document_id,
        "job_id": job.id,
        "status": job.status,
        "items": [
            {
                "clause_id": item.clause.clause_id,
                "reference_id": item.reference_id,
                "display_label": item.display_label,
                "summary": item.summary,
                "expert_review_recommended": (
                    item.expert_review_recommended
                ),
            }
            for item in items
        ],
    }
