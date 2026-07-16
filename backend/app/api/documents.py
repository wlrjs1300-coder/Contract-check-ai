from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

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
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file must be UTF-8 encoded.",
        ) from exc

    return {
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "character_count": len(text),
        "status": "uploaded",
    }
