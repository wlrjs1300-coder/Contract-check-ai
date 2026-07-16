from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.services.clause_splitter import split_clauses
from backend.app.services.document_store import documents

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 1 * 1024 * 1024
ALLOWED_SUFFIXES = {".txt"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, object]:
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

    document = {
        "document_id": document_id,
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "character_count": len(text),
        "status": "processed",
        "clause_count": clause_result["clause_count"],
        "clauses": clause_result["clauses"],
        "unclassified_sections": clause_result["unclassified_sections"],
        "document_warnings": clause_result["document_warnings"],
    }

    documents[document_id] = document
    return document


@router.get("/{document_id}")
def get_document(document_id: str) -> dict[str, object]:
    document = documents.get(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return document
