from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.database import get_db
from backend.app.db.models import Extraction, ExtractionPage
from backend.app.schemas.extractions import (
    ExtractionErrorResponse,
    ExtractionPageResponse,
    ExtractionResponse,
)
from backend.app.services.extraction_temp_files import (
    OriginalCleanupError,
    RequestDirectory,
    UploadSizeLimitExceededError,
    cleanup_request_directory,
    create_request_directory,
    create_server_file_path,
    write_upload_to_temp,
)
from backend.app.services.pdf_extraction import (
    MAX_PDF_SIZE_BYTES,
    PDFExtractionError,
    extract_text_pdf,
)


router = APIRouter(prefix="/extractions", tags=["extractions"])
PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream", None, ""}
ERROR_RESPONSES = {
    400: {"model": ExtractionErrorResponse},
    404: {"model": ExtractionErrorResponse},
    413: {"model": ExtractionErrorResponse},
    422: {"model": ExtractionErrorResponse},
    500: {"model": ExtractionErrorResponse},
}


def _error_detail(
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
    }


def _safe_filename_display(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", basename).strip()
    return (sanitized or "document.pdf")[:255]


def _serialize_extraction(extraction: Extraction) -> ExtractionResponse:
    pages = sorted(extraction.pages, key=lambda page: page.page_number)
    return ExtractionResponse(
        extraction_id=extraction.id,
        filename_display=extraction.filename_display,
        source_type=extraction.source_type,
        size_bytes=extraction.size_bytes,
        page_count=extraction.page_count,
        extraction_status=extraction.status,
        extraction_method=extraction.method,
        pages=[
            ExtractionPageResponse(
                page_number=page.page_number,
                extraction_method=page.method,
                text=page.text,
                warnings=page.warnings,
                requires_user_review=page.requires_user_review,
            )
            for page in pages
        ],
        warnings=extraction.warnings,
        requires_user_review=extraction.requires_user_review,
        created_at=extraction.created_at,
    )


@router.post(
    "",
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_extraction(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ExtractionResponse:
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "unsupported_file_type",
                "Only PDF files are supported for text extraction.",
            ),
        )

    if file.content_type not in PDF_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "file_type_mismatch",
                "The uploaded file does not match the PDF format.",
            ),
        )

    request_directory: RequestDirectory | None = None
    source_path: Path | None = None
    extracted_pdf = None
    size_bytes = 0
    pending_error: HTTPException | None = None

    try:
        request_directory = create_request_directory()
        source_path = create_server_file_path(request_directory)
        size_bytes = await write_upload_to_temp(
            file,
            source_path,
            max_size_bytes=MAX_PDF_SIZE_BYTES,
        )

        if size_bytes == 0:
            raise PDFExtractionError(
                "empty_document",
                "The uploaded PDF file is empty.",
            )

        extracted_pdf = extract_text_pdf(source_path)
    except UploadSizeLimitExceededError:
        pending_error = HTTPException(
            status_code=413,
            detail=_error_detail(
                "file_size_limit_exceeded",
                "The PDF file exceeds the 20 MiB limit.",
            ),
        )
    except PDFExtractionError as exc:
        pending_error = HTTPException(
            status_code=exc.status_code,
            detail=_error_detail(
                exc.code,
                exc.message,
                retryable=exc.retryable,
            ),
        )
    except OriginalCleanupError as exc:
        raise HTTPException(
            status_code=500,
            detail=_error_detail(
                "original_cleanup_failed",
                "The uploaded file could not be safely removed.",
            ),
        ) from exc
    except (OSError, RuntimeError):
        pending_error = HTTPException(
            status_code=500,
            detail=_error_detail(
                "temporary_storage_unavailable",
                "Temporary document storage is unavailable.",
                retryable=True,
            ),
        )

    if request_directory is not None:
        try:
            cleanup_request_directory(request_directory)
        except OriginalCleanupError as exc:
            raise HTTPException(
                status_code=500,
                detail=_error_detail(
                    "original_cleanup_failed",
                    "The uploaded file could not be safely removed.",
                ),
            ) from exc

    if pending_error is not None:
        raise pending_error

    if extracted_pdf is None:
        raise HTTPException(
            status_code=500,
            detail=_error_detail(
                "extraction_failed",
                "The PDF extraction could not be completed.",
                retryable=True,
            ),
        )

    extraction = Extraction(
        id=str(uuid4()),
        filename_display=_safe_filename_display(filename),
        source_type="pdf",
        size_bytes=size_bytes,
        page_count=len(extracted_pdf.pages),
        status="review_required",
        method="direct",
        warnings=list(extracted_pdf.warnings),
        requires_user_review=True,
    )
    extraction.pages.extend(
        ExtractionPage(
            page_number=page.page_number,
            method="direct",
            text=page.text,
            warnings=list(page.warnings),
            requires_user_review=True,
        )
        for page in extracted_pdf.pages
    )
    db.add(extraction)
    db.commit()
    db.refresh(extraction)
    return _serialize_extraction(extraction)


@router.get(
    "/{extraction_id}",
    response_model=ExtractionResponse,
    responses=ERROR_RESPONSES,
)
def get_extraction(
    extraction_id: str,
    db: Session = Depends(get_db),
) -> ExtractionResponse:
    statement = (
        select(Extraction)
        .options(selectinload(Extraction.pages))
        .where(Extraction.id == extraction_id)
    )
    extraction = db.scalar(statement)

    if extraction is None:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                "extraction_not_found",
                "The extraction was not found.",
            ),
        )

    return _serialize_extraction(extraction)
