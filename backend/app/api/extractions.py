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
from backend.app.services.image_ocr import (
    MAX_IMAGE_COUNT,
    MAX_IMAGE_FILE_BYTES,
    MAX_REQUEST_SIZE_BYTES,
    ImageExtractionError,
    OcrAdapter,
    UnavailableOcrAdapter,
    canonical_format_from_extension,
    extract_images,
    prepare_image,
    validate_content_type,
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
    503: {"model": ExtractionErrorResponse},
    504: {"model": ExtractionErrorResponse},
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


def _image_error_detail(
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> dict[str, object]:
    return {
        **_error_detail(code, message, retryable=retryable),
        "analysis_blocked": True,
    }


def _safe_filename_display(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    sanitized = re.sub(r"[\x00-\x1f\x7f]", "", basename).strip()
    return (sanitized or "document.pdf")[:255]


def _serialize_extraction(extraction: Extraction) -> ExtractionResponse:
    pages = sorted(extraction.pages, key=lambda page: page.page_number)
    extraction_data = extraction.extra_data or {}
    return ExtractionResponse(
        extraction_id=extraction.id,
        filename_display=extraction.filename_display,
        source_type=extraction.source_type,
        size_bytes=extraction.size_bytes,
        page_count=extraction.page_count,
        total_pages=extraction.page_count,
        completed_pages=extraction_data.get("completed_pages", len(pages)),
        failed_pages=extraction_data.get("failed_pages", 0),
        total_text_length=extraction_data.get(
            "total_text_length",
            sum(len(page.text) for page in pages),
        ),
        extraction_status=extraction.status,
        extraction_method=extraction.method,
        pages=[
            ExtractionPageResponse(
                page_number=page.page_number,
                extraction_method=page.method,
                text=page.text,
                text_length=len(page.text),
                page_id=(page.extra_data or {}).get("page_id"),
                source_format=(page.extra_data or {}).get("source_format"),
                normalized_width=(page.extra_data or {}).get("normalized_width"),
                normalized_height=(page.extra_data or {}).get("normalized_height"),
                blocks=(page.extra_data or {}).get("blocks", []),
                warnings=page.warnings,
                requires_user_review=page.requires_user_review,
                review_required=page.requires_user_review,
                analysis_blocked=(page.extra_data or {}).get(
                    "analysis_blocked",
                    True,
                ),
                failure=(page.extra_data or {}).get("failure"),
            )
            for page in pages
        ],
        warnings=extraction.warnings,
        requires_user_review=extraction.requires_user_review,
        review_required=extraction.requires_user_review,
        analysis_blocked=extraction_data.get("analysis_blocked", True),
        created_at=extraction.created_at,
        updated_at=extraction.created_at,
    )


def get_ocr_adapter() -> OcrAdapter:
    return UnavailableOcrAdapter()


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


@router.post(
    "/images",
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_image_extraction(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    ocr_adapter: OcrAdapter = Depends(get_ocr_adapter),
) -> ExtractionResponse:
    if not files or len(files) > MAX_IMAGE_COUNT:
        raise HTTPException(
            status_code=413,
            detail=_image_error_detail(
                "request_image_count_exceeded",
                f"A request may contain at most {MAX_IMAGE_COUNT} images.",
            ),
        )

    expected_formats: list[str] = []
    for upload in files:
        try:
            expected_format = canonical_format_from_extension(upload.filename or "")
            validate_content_type(upload.content_type, expected_format)
        except ImageExtractionError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=_image_error_detail(
                    exc.code,
                    exc.message,
                    retryable=exc.retryable,
                ),
            ) from exc
        expected_formats.append(expected_format)

    request_directory: RequestDirectory | None = None
    extracted_images = None
    total_size_bytes = 0
    pending_error: HTTPException | None = None

    try:
        request_directory = create_request_directory()
        source_paths: list[Path] = []
        for upload, expected_format in zip(files, expected_formats, strict=True):
            source_path = create_server_file_path(
                request_directory,
                suffix=f".{expected_format}",
            )
            try:
                size_bytes = await write_upload_to_temp(
                    upload,
                    source_path,
                    max_size_bytes=MAX_IMAGE_FILE_BYTES,
                )
            except UploadSizeLimitExceededError as exc:
                raise ImageExtractionError(
                    "image_too_large",
                    "An image exceeds the allowed file size.",
                    status_code=413,
                ) from exc
            if size_bytes == 0:
                raise ImageExtractionError(
                    "invalid_image_signature",
                    "An uploaded image is empty.",
                )
            total_size_bytes += size_bytes
            if total_size_bytes > MAX_REQUEST_SIZE_BYTES:
                raise ImageExtractionError(
                    "request_total_size_exceeded",
                    "The request exceeds the allowed total file size.",
                    status_code=413,
                )
            source_paths.append(source_path)

        prepared_images = [
            prepare_image(
                path,
                expected_format=expected_format,
                page_number=index,
            )
            for index, (path, expected_format) in enumerate(
                zip(source_paths, expected_formats, strict=True),
                start=1,
            )
        ]
        extracted_images = extract_images(prepared_images, ocr_adapter)
    except ImageExtractionError as exc:
        pending_error = HTTPException(
            status_code=exc.status_code,
            detail=_image_error_detail(
                exc.code,
                exc.message,
                retryable=exc.retryable,
            ),
        )
    except OriginalCleanupError as exc:
        raise HTTPException(
            status_code=500,
            detail=_image_error_detail(
                "original_cleanup_failed",
                "The uploaded files could not be safely removed.",
            ),
        ) from exc
    except (OSError, RuntimeError, ValueError):
        pending_error = HTTPException(
            status_code=500,
            detail=_image_error_detail(
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
                detail=_image_error_detail(
                    "original_cleanup_failed",
                    "The uploaded files could not be safely removed.",
                ),
            ) from exc

    if pending_error is not None:
        raise pending_error
    if extracted_images is None:
        raise HTTPException(
            status_code=500,
            detail=_image_error_detail(
                "ocr_failed",
                "The image text extraction could not be completed.",
                retryable=True,
            ),
        )

    extraction = Extraction(
        id=str(uuid4()),
        filename_display="image-upload",
        source_type="image",
        size_bytes=total_size_bytes,
        page_count=len(extracted_images.pages),
        status="review_required",
        method="ocr",
        warnings=list(extracted_images.warnings),
        requires_user_review=extracted_images.review_required,
        extra_data={
            "completed_pages": len(extracted_images.pages),
            "failed_pages": 0,
            "total_text_length": extracted_images.total_text_length,
            "analysis_blocked": extracted_images.analysis_blocked,
        },
    )
    extraction.pages.extend(
        ExtractionPage(
            page_number=page.page_number,
            method="ocr",
            text=page.text,
            warnings=list(page.warnings),
            requires_user_review=page.review_required,
            extra_data={
                "page_id": page.page_id,
                "source_format": next(
                    prepared.canonical_format
                    for prepared in prepared_images
                    if prepared.page_number == page.page_number
                ),
                "normalized_width": page.normalized_width,
                "normalized_height": page.normalized_height,
                "analysis_blocked": page.analysis_blocked,
                "failure": None,
                "blocks": [
                    {
                        "block_index": block.block_index,
                        "text": block.text,
                        "confidence": block.confidence,
                        "bbox": block.bbox,
                        "reading_order": block.reading_order,
                    }
                    for block in page.blocks
                ],
            },
        )
        for page in extracted_images.pages
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
