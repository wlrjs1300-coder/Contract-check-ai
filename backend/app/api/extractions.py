from __future__ import annotations

import os
import re
from datetime import UTC, datetime
import hashlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.db.database import get_db
from backend.app.db.models import Extraction, ExtractionPage
from backend.app.schemas.extractions import (
    ExtractionErrorResponse,
    ExtractionReviewPageResponse,
    ExtractionReviewResponse,
    ExtractionPageResponse,
    ExtractionResponse,
    ExtractionConfirmationResponse,
    PageReviewPatchRequest,
)
from backend.app.services.image_ocr import (
    MAX_IMAGE_COUNT,
    MAX_IMAGE_FILE_BYTES,
    MAX_REQUEST_SIZE_BYTES,
    OCR_TIMEOUT_SECONDS,
    ImageExtractionError,
    OcrFailure,
    OcrPageInput,
    OcrPageResult,
    OcrAdapter,
    UnavailableOcrAdapter,
    SyntheticOcrAdapter,
    LocalKoreanOcrAdapter,
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
    refresh_request_directory_lease,
    create_server_file_path,
    write_upload_to_temp,
)
from backend.app.services.pdf_extraction import (
    MAX_PDF_SIZE_BYTES,
    PDFExtractionError,
    PDF_PAGE_CLASSIFICATION_DIRECT_USABLE,
    PDF_PAGE_CLASSIFICATION_BLANK_CANDIDATE,
    ExtractedPage,
    MAX_PDF_RENDER_PIXELS,
    MAX_RENDER_TIMEOUT_SECONDS as PDF_RENDER_TIMEOUT_SECONDS,
    UnavailablePdfRenderer,
    SyntheticPdfRenderer,
    PdfPageRenderer,
    PdfRenderRequest,
    extract_text_pdf,
)


MAX_PAGE_REVIEW_TEXT = 200_000
MAX_DOCUMENT_REVIEW_TEXT = 1_000_000



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


def _to_iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat()


def _stable_checksum(values: list[str]) -> str:
    hasher = hashlib.sha256()
    for value in values:
        hasher.update(value.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def _extract_review_data(
    extraction: Extraction,
) -> dict[str, object]:
    extraction_data = extraction.extra_data or {}
    return {
        "review_status": extraction_data.get("review_status", "pending"),
        "review_version": extraction_data.get("review_version", 1),
        "can_confirm": extraction_data.get("can_confirm", False),
        "blocking_reasons": list(extraction_data.get("blocking_reasons", [])),
        "confirmed_at": extraction_data.get("confirmed_at"),
    }


def _extract_page_review_data(
    page: ExtractionPage,
) -> dict[str, object]:
    page_data = page.extra_data or {}
    return {
        "review_status": page_data.get("review_status", "pending"),
        "review_version": page_data.get("review_version", 1),
        "reviewed_text": page_data.get("reviewed_text"),
        "text_changed": bool(page_data.get("text_changed", False)),
        "reviewed_at": page_data.get("reviewed_at"),
        "confirmed_at": page_data.get("confirmed_at"),
        "final_text": page_data.get("final_text"),
        "final_text_preview": (page_data.get("final_text") or page.text)[:80],
    }


def _build_review_summary(
    extraction: Extraction,
) -> dict[str, int | bool | list[str] | str]:
    pages = extraction.pages
    required_pages = 0
    reviewed = 0
    edited = 0
    failed = 0
    blocked = False
    blocking_reasons: list[str] = []

    for page in pages:
        page_review_data = _extract_page_review_data(page)
        is_required = page.requires_user_review
        page_status = page_review_data["review_status"]
        if page_data := page.extra_data:
            if page_data.get("analysis_blocked") is True:
                blocked = True
                blocked_reason = page_data.get("failure")
                if blocked_reason and blocked_reason not in blocking_reasons:
                    blocking_reasons.append(blocked_reason)
        if is_required:
            required_pages += 1
            if page_status in {"reviewed", "edited"}:
                reviewed += 1
            elif page_status == "pending":
                pass
        if page_status == "edited":
            edited += 1
        if (page_data or {}).get("failure"):
            failed += 1

    if required_pages == 0:
        extraction_review_status = "not_required"
    elif extraction.requires_user_review and failed > 0:
        if "extraction_has_failed_pages" not in blocking_reasons:
            blocking_reasons.append("extraction_has_failed_pages")

    if extraction.status == "confirmed":
        extraction_review_status = "confirmed"
    elif required_pages == 0:
        extraction_review_status = "not_required"
    elif reviewed == 0:
        extraction_review_status = "pending"
    elif reviewed < required_pages:
        extraction_review_status = "partially_reviewed"
    else:
        extraction_review_status = "ready_to_confirm"

    return {
        "required_pages": required_pages,
        "reviewed_pages": reviewed,
        "edited_pages": edited,
        "failed_pages": failed,
        "blocked": blocked,
        "blocking_reasons": blocking_reasons,
        "extraction_review_status": extraction_review_status,
    }


class _LeaseRefreshError(RuntimeError):
    """임시 저장소 Lease 갱신 실패."""


def _refresh_lease_or_fail(request_directory: RequestDirectory) -> RequestDirectory:
    try:
        return refresh_request_directory_lease(request_directory)
    except OriginalCleanupError as exc:
        raise _LeaseRefreshError from exc


def _serialize_extraction(extraction: Extraction) -> ExtractionResponse:
    pages = sorted(extraction.pages, key=lambda page: page.page_number)
    extraction_data = extraction.extra_data or {}
    summary = _build_review_summary(extraction)
    extraction_review_status = summary["extraction_review_status"]
    review_metadata = _extract_review_data(extraction)

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
                review_status=_extract_page_review_data(page)["review_status"],
                review_version=_extract_page_review_data(page)["review_version"],
                reviewed_text=_extract_page_review_data(page)["reviewed_text"],
                text_changed=_extract_page_review_data(page)["text_changed"],
                reviewed_at=_extract_page_review_data(page)["reviewed_at"],
                final_text_preview=_extract_page_review_data(page)["final_text_preview"],
                failure=(page.extra_data or {}).get("failure"),
            )
            for page in pages
        ],
        warnings=extraction.warnings,
        requires_user_review=extraction.requires_user_review,
        review_required=extraction.requires_user_review,
        analysis_blocked=extraction_data.get("analysis_blocked", True),
        review_status=extraction_review_status,
        review_version=review_metadata["review_version"],
        can_confirm=review_metadata["can_confirm"],
        reviewed_pages=summary["reviewed_pages"],
        edited_pages=summary["edited_pages"],
        required_review_pages=summary["required_pages"],
        blocking_reasons=summary["blocking_reasons"],
        confirmed_at=review_metadata["confirmed_at"],
        final_text_length=extraction_data.get(
            "final_total_text_length",
            extraction_data.get("total_text_length", 0),
        ),
        created_at=extraction.created_at,
        updated_at=extraction.created_at,
    )


def _get_extraction_with_pages(
    extraction_id: str,
    db: Session,
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
            detail=_error_detail(
                "extraction_not_found",
                "The extraction was not found.",
            ),
        )

    return extraction


def _parse_version_value(
    if_match: str | None,
    payload_version: int | None,
    *,
    fallback_error_code: str = "invalid_if_match",
) -> int:
    if payload_version is not None:
        return payload_version

    if if_match is None:
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                fallback_error_code,
                "A matching version is required.",
            ),
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
            detail=_error_detail(
                fallback_error_code,
                "The version header could not be parsed.",
            ),
        ) from exc


def get_ocr_adapter() -> OcrAdapter:
    app_env = (os.getenv("APP_ENV") or "production").lower().strip()
    adapter_mode = (os.getenv("OCR_ADAPTER") or "").strip().lower()

    if app_env == "test":
        if adapter_mode in {"local", "local_korean", "tesseract"}:
            return LocalKoreanOcrAdapter()
        return SyntheticOcrAdapter()

    if app_env in {"production", "development"} and adapter_mode in {
        "",
        "local",
        "local_korean",
        "tesseract",
    }:
        try:
            return LocalKoreanOcrAdapter()
        except OcrFailure:
            return UnavailableOcrAdapter()
    if adapter_mode == "synthetic":
        raise RuntimeError(
            "Synthetic OCR adapter is test-only and cannot be used in non-test environment."
        )
    return UnavailableOcrAdapter()


def get_pdf_renderer() -> PdfPageRenderer:
    if os.getenv("APP_ENV") == "test":
        return SyntheticPdfRenderer()
    return UnavailablePdfRenderer()


def _run_pdf_ocr_with_timeout(
    adapter: OcrAdapter,
    page: OcrPageInput,
    *,
    timeout_seconds: float,
) -> OcrPageResult:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-page")
    future = executor.submit(adapter.recognize, page)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        raise ImageExtractionError(
            "pdf_page_render_timeout",
            "The PDF page text extraction timed out.",
            status_code=504,
            retryable=True,
        ) from exc
    except OcrFailure as exc:
        code = exc.code if exc.code == "ocr_unavailable" else "ocr_failed"
        raise ImageExtractionError(
            code,
            "The PDF page text extraction could not be completed.",
            status_code=503 if code == "ocr_unavailable" else 500,
            retryable=True,
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _process_pdf_pages(
    pdf_pages: tuple[ExtractedPage, ...],
    source_path: Path,
    request_directory: RequestDirectory,
    ocr_adapter: OcrAdapter,
    pdf_renderer: PdfPageRenderer,
) -> tuple[list[dict[str, object]], dict[str, int], tuple[str, ...], bool]:
    processed_pages: list[dict[str, object]] = []
    completed_pages = 0
    failed_pages = 0
    direct_pages = 0
    ocr_pages = 0
    review_required_pages = 0
    total_text_length = 0
    document_analysis_blocked = False

    for page in pdf_pages:
        page_review_required = bool(page.review_required)
        page_classification = page.classification
        page_method = "direct"
        page_failure: str | None = None
        page_warning_list = list(page.warnings)
        page_blocks: list[dict[str, object]] = []
        source_format = None
        normalized_width: int | None = None
        normalized_height: int | None = None
        page_text = page.text
        count_as_completed = bool(page_text.strip())

        if page.classification != PDF_PAGE_CLASSIFICATION_DIRECT_USABLE:
            page_review_required = True
            should_ocr = True
            request_directory = _refresh_lease_or_fail(request_directory)

            if should_ocr:
                try:
                    render_request = PdfRenderRequest(
                        request_directory=request_directory,
                        source_path=source_path,
                        page_number=page.page_number,
                        page_id=page.page_id,
                    )
                    rendered = pdf_renderer.render(render_request)
                    if (
                        rendered.page_number != page.page_number
                        or rendered.page_id != page.page_id
                    ):
                        raise ImageExtractionError(
                            "pdf_page_render_failed",
                            "The PDF page rendering returned a mismatched page identity.",
                            status_code=500,
                        )
                    if rendered.pixel_count > MAX_PDF_RENDER_PIXELS:
                        raise ImageExtractionError(
                            "pdf_render_limit_exceeded",
                            "The PDF page was too large to render.",
                            status_code=422,
                            retryable=True,
                        )

                    ocr_result = _run_pdf_ocr_with_timeout(
                        ocr_adapter,
                        OcrPageInput(
                            page_number=page.page_number,
                            page_id=page.page_id,
                            image_bytes=rendered.image_bytes,
                            width=rendered.width,
                            height=rendered.height,
                        ),
                        timeout_seconds=min(
                            OCR_TIMEOUT_SECONDS,
                            PDF_RENDER_TIMEOUT_SECONDS,
                        ),
                    )
                    if not ocr_result.text.strip():
                        raise ImageExtractionError(
                            "empty_ocr_result",
                            "No text could be extracted from an image.",
                            status_code=422,
                        )
                    page_warning_list.extend(ocr_result.warnings)

                    for expected_index, block in enumerate(ocr_result.blocks):
                        if block.block_index != expected_index or block.reading_order != expected_index:
                            raise ImageExtractionError(
                                "ocr_result_block_order_mismatch",
                                "The PDF page OCR result block order is invalid.",
                                status_code=500,
                            )

                        page_blocks.append(
                            {
                                "block_index": block.block_index,
                                "text": block.text,
                                "confidence": block.confidence,
                                "bbox": block.bbox,
                                "reading_order": block.reading_order,
                            }
                        )

                    page_method = "ocr"
                    page_text = ocr_result.text
                    source_format = "png"
                    normalized_width = rendered.normalized_width
                    normalized_height = rendered.normalized_height
                    count_as_completed = bool(page_text.strip())

                    if ocr_result.confidence is None:
                        page_warning_list.append("ocr_confidence_unavailable")
                    elif ocr_result.confidence < 0.8:
                        page_warning_list.append("ocr_confidence_low")
                except PDFExtractionError as exc:
                    page_failure = exc.code
                    page_warning_list.append(exc.code)
                except ImageExtractionError as exc:
                    page_failure = exc.code
                    page_warning_list.append(exc.code)

        if count_as_completed:
            completed_pages += 1
            total_text_length += len(page_text)
            if page_method == "ocr":
                ocr_pages += 1
            else:
                direct_pages += 1

        if page_failure is not None:
            failed_pages += 1
            document_analysis_blocked = True

        if page_review_required:
            review_required_pages += 1
            document_analysis_blocked = True

        if page.classification == PDF_PAGE_CLASSIFICATION_BLANK_CANDIDATE:
            page_warning_list.append("empty_page_text")

        processed_pages.append(
            {
                "page_number": page.page_number,
                "classification": page_classification,
                "method": page_method,
                "text": page_text,
                "warnings": list(dict.fromkeys(page_warning_list)),
                "analysis_blocked": bool(page_failure is not None or page_review_required),
                "failure": page_failure,
                "page_id": page.page_id,
                "requires_user_review": page_review_required,
                "source_format": source_format,
                "normalized_width": normalized_width,
                "normalized_height": normalized_height,
                "blocks": page_blocks,
            }
        )

    summary = {
        "completed_pages": completed_pages,
        "failed_pages": failed_pages,
        "direct_pages": direct_pages,
        "ocr_pages": ocr_pages,
        "review_required_pages": review_required_pages,
        "total_text_length": total_text_length,
    }

    if completed_pages == 0:
        document_analysis_blocked = True

    return (
        processed_pages,
        summary,
        (),
        document_analysis_blocked,
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
    ocr_adapter: OcrAdapter = Depends(get_ocr_adapter),
    pdf_renderer: PdfPageRenderer = Depends(get_pdf_renderer),
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
    processed_pages: list[dict[str, object]] = []
    extraction_summary: dict[str, int] = {}

    try:
        request_directory = create_request_directory()
        source_path = create_server_file_path(request_directory)
        size_bytes = await write_upload_to_temp(
            file,
            source_path,
            max_size_bytes=MAX_PDF_SIZE_BYTES,
        )
        request_directory = _refresh_lease_or_fail(request_directory)

        if size_bytes == 0:
            raise PDFExtractionError(
                "empty_document",
                "The uploaded PDF file is empty.",
            )

        extracted_pdf = extract_text_pdf(source_path)
        processed_pages, extraction_summary, _, _ = (
            _process_pdf_pages(
                tuple(extracted_pdf.pages),
                source_path,
                request_directory,
                ocr_adapter,
                pdf_renderer,
            )
        )
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
    except _LeaseRefreshError:
        pending_error = HTTPException(
            status_code=500,
            detail=_error_detail(
                "temporary_storage_unavailable",
                "Temporary storage lease renewal failed.",
                retryable=True,
            ),
        )
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

    if not processed_pages:
        raise HTTPException(
            status_code=500,
            detail=_error_detail(
                "extraction_failed",
                "The PDF extraction could not be completed.",
                retryable=True,
            ),
        )

    extraction_method = "direct"
    if extraction_summary.get("ocr_pages", 0) > 0:
        extraction_method = "ocr" if extraction_summary.get("direct_pages") == 0 else "mixed"
    requires_user_review = extraction_summary.get("review_required_pages", 0) > 0

    extraction = Extraction(
        id=str(uuid4()),
        filename_display=_safe_filename_display(filename),
        source_type="pdf",
        size_bytes=size_bytes,
        page_count=len(processed_pages),
        status="review_required",
        method=extraction_method,
        warnings=list(extracted_pdf.warnings),
        requires_user_review=requires_user_review,
        extra_data={
            **extraction_summary,
            "analysis_blocked": requires_user_review or extraction_summary.get(
                "failed_pages",
                0,
            )
            > 0,
            "review_required": requires_user_review,
            "review_status": "confirmed" if not requires_user_review else "pending",
            "review_version": 1,
            "can_confirm": (
                extraction_summary.get("failed_pages", 0) == 0
                and requires_user_review is False
            ),
            "blocking_reasons": [],
        },
    )
    extraction.pages.extend(
        ExtractionPage(
            page_number=page["page_number"],
            method=page["method"],
            text=page["text"],
            warnings=page["warnings"],
            requires_user_review=page["requires_user_review"],
            extra_data={
                "page_id": page["page_id"],
                "source_format": page["source_format"],
                "normalized_width": page["normalized_width"],
                "normalized_height": page["normalized_height"],
                "analysis_blocked": page["analysis_blocked"],
                "failure": page["failure"],
                "blocks": page["blocks"],
                "classification": page["classification"],
                "review_status": "not_required"
                if not page["requires_user_review"]
                else "pending",
                "review_version": 1,
                "reviewed_text": None,
                "text_changed": False,
                "reviewed_at": None,
                "confirmed_at": None,
                "final_text": None,
            },
        )
        for page in processed_pages
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
            request_directory = _refresh_lease_or_fail(request_directory)

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
        request_directory = _refresh_lease_or_fail(request_directory)
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
    except _LeaseRefreshError:
        pending_error = HTTPException(
            status_code=500,
            detail=_image_error_detail(
                "temporary_storage_unavailable",
                "Temporary storage lease renewal failed.",
                retryable=True,
            ),
        )
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
            "review_required": extracted_images.review_required,
            "review_status": "pending" if extracted_images.review_required else "not_required",
            "review_version": 1,
            "can_confirm": (
                extracted_images.review_required is False
                and extracted_images.analysis_blocked is False
            ),
            "blocking_reasons": [],
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
                "review_status": "not_required"
                if not page.review_required
                else "pending",
                "review_version": 1,
                "reviewed_text": None,
                "text_changed": False,
                "reviewed_at": None,
                "confirmed_at": None,
                "final_text": None,
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
    extraction = _get_extraction_with_pages(extraction_id, db)
    return _serialize_extraction(extraction)


@router.get(
    "/{extraction_id}/review",
    response_model=ExtractionReviewResponse,
    responses=ERROR_RESPONSES,
)
def get_extraction_review(
    extraction_id: str,
    db: Session = Depends(get_db),
) -> ExtractionReviewResponse:
    extraction = _get_extraction_with_pages(extraction_id, db)
    summary = _build_review_summary(extraction)
    extraction_data = extraction.extra_data or {}

    review_pages: list[ExtractionReviewPageResponse] = []
    for page in sorted(extraction.pages, key=lambda item: item.page_number):
        page_data = _extract_page_review_data(page)
        page_extra = page.extra_data or {}
        review_pages.append(
            ExtractionReviewPageResponse(
                page_id=str(page_extra.get("page_id", page.page_number)),
                page_number=page.page_number,
                method=page.method,
                classification=page_extra.get("classification"),
                original_text=page.text,
                reviewed_text=page_data["reviewed_text"],
                final_text_preview=page_data["final_text_preview"],
                text_changed=bool(page_data["text_changed"]),
                review_status=page_data["review_status"],
                review_version=page_data["review_version"],
                reviewed_at=page_data["reviewed_at"],
                confirmed_at=page_data["confirmed_at"],
                warnings=page.warnings,
                blocks=page_extra.get("blocks", []),
                failure=page_extra.get("failure"),
                analysis_blocked=bool(page_extra.get("analysis_blocked", True)),
            )
        )

    return ExtractionReviewResponse(
        extraction_id=extraction.id,
        review_status=summary["extraction_review_status"],
        review_version=int(extraction_data.get("review_version", 1)),
        review_required=extraction.requires_user_review,
        can_confirm=_build_can_confirm(extraction, summary),
        review_completed=summary["extraction_review_status"] in {
            "ready_to_confirm",
            "confirmed",
        },
        total_pages=len(extraction.pages),
        required_review_pages=summary["required_pages"],
        reviewed_pages=summary["reviewed_pages"],
        edited_pages=summary["edited_pages"],
        failed_pages=summary["failed_pages"],
        blocked=summary["blocked"],
        blocking_reasons=summary["blocking_reasons"],
        pages=review_pages,
    )


def _build_can_confirm(
    extraction: Extraction,
    summary: dict[str, int | bool | list[str] | str],
) -> bool:
    required_pages = int(summary["required_pages"])
    reviewed_pages = int(summary["reviewed_pages"])
    failed_pages = int(summary["failed_pages"])
    return (
        extraction.requires_user_review is False
        and failed_pages == 0
        or (
            required_pages == reviewed_pages
            and failed_pages == 0
            and not _extraction_review_stale(extraction)
        )
    )


def _extraction_review_stale(extraction: Extraction) -> bool:
    # Keep behavior strict if any required page still pending/blocked.
    pages = _build_review_summary(extraction)
    return pages["extraction_review_status"] in {"pending", "partially_reviewed"}


def _validate_review_text(text: str, *, field_name: str = "reviewed_text") -> None:
    if "\x00" in text:
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "invalid_review_text",
                f"The {field_name} must not contain null bytes.",
            ),
        )

    if len(text) > MAX_PAGE_REVIEW_TEXT:
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "invalid_review_text",
                f"The {field_name} exceeds maximum allowed length.",
            ),
        )

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "invalid_review_text",
                "The review text cannot be empty.",
            ),
        )


def _build_confirmation_snapshot(
    extraction: Extraction,
) -> tuple[list[dict[str, object]], int, int, int]:
    pages = sorted(extraction.pages, key=lambda page: page.page_number)
    if not pages:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "extraction_review_incomplete",
                "No pages are available for confirmation.",
            ),
        )

    expected = list(range(1, len(pages) + 1))
    page_numbers = [page.page_number for page in pages]
    if sorted(page_numbers) != expected:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "extraction_review_incomplete",
                "Page order is invalid for confirmation.",
            ),
        )

    page_ids = [str((page.extra_data or {}).get("page_id", page.page_number)) for page in pages]
    if len(set(page_ids)) != len(page_ids):
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "extraction_review_incomplete",
                "Duplicate page identifiers were found.",
            ),
        )

    snapshot: list[dict[str, object]] = []
    reviewed_count = 0
    edited_count = 0
    confirmed_pages = 0
    for page in pages:
        page_data = page.extra_data or {}
        review_status = page_data.get("review_status", "pending")
        page_requires_review = bool(page.requires_user_review)
        failure = page_data.get("failure")
        if failure:
            raise HTTPException(
                status_code=409,
                detail=_error_detail(
                    "extraction_has_failed_pages",
                    "Extraction cannot be confirmed because one or more pages failed.",
                ),
            )

        if page_requires_review and review_status not in {"reviewed", "edited"}:
            raise HTTPException(
                status_code=409,
                detail=_error_detail(
                    "extraction_review_incomplete",
                    "Not all required pages have been reviewed.",
                ),
            )

        final_text = (
            page_data.get("reviewed_text")
            if review_status == "edited"
            else page.text
        )
        if final_text is None or not str(final_text).strip():
            raise HTTPException(
                status_code=409,
                detail=_error_detail(
                    "invalid_review_text",
                    "All final page texts must be non-empty.",
                ),
            )

        final_text = str(final_text)
        if len(final_text) > MAX_PAGE_REVIEW_TEXT:
            raise HTTPException(
                status_code=400,
                detail=_error_detail(
                    "invalid_review_text",
                    "Final confirmed text exceeds page limit.",
                ),
            )

        is_changed = bool(page_data.get("text_changed", False))
        if is_changed:
            edited_count += 1
        if page_requires_review:
            reviewed_count += 1

        snapshot.append(
            {
                "page_id": str((page_data.get("page_id", page.page_number))),
                "page_number": page.page_number,
                "final_text": final_text,
                "text_source": "edited" if is_changed else "original",
                "text_changed": is_changed,
                "method": page.method,
                "warnings": page.warnings,
                "blocks": (page_data.get("blocks") or []),
            }
        )
        confirmed_pages += 1

    if any(len(item["final_text"]) > MAX_PAGE_REVIEW_TEXT for item in snapshot):
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "invalid_review_text",
                "The confirmed text exceeds allowed per-page limit.",
            ),
        )

    total_text_length = sum(len(item["final_text"]) for item in snapshot)
    if total_text_length > MAX_DOCUMENT_REVIEW_TEXT:
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "invalid_review_text",
                "The confirmed document text exceeds total length limit.",
            ),
        )

    return snapshot, confirmed_pages, reviewed_count, edited_count


@router.patch(
    "/{extraction_id}/pages/{page_id}/review",
    response_model=ExtractionReviewPageResponse,
    responses=ERROR_RESPONSES,
)
def patch_extraction_page_review(
    extraction_id: str,
    page_id: str,
    payload: PageReviewPatchRequest,
    db: Session = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ExtractionReviewPageResponse:
    extraction = _get_extraction_with_pages(extraction_id, db)
    if extraction.status == "confirmed":
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "extraction_already_confirmed",
                "The extraction has already been confirmed.",
            ),
        )
    if not extraction.requires_user_review:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "extraction_not_reviewable",
                "The extraction does not require review.",
            ),
        )

    candidate_pages = [
        page for page in extraction.pages if page.extra_data.get("page_id") == page_id
    ]
    if not candidate_pages:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                "page_not_found",
                "The extraction page was not found.",
            ),
        )

    page = candidate_pages[0]
    page_data = page.extra_data or {}
    if not page.requires_user_review:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "page_not_reviewable",
                "The page does not require manual review.",
            ),
        )

    request_version = _parse_version_value(
        if_match=if_match,
        payload_version=payload.version,
        fallback_error_code="page_review_version_mismatch",
    )
    current_version = int(page_data.get("review_version", 1))
    if request_version != current_version:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "page_review_conflict",
                "The page review version is stale.",
            ),
        )

    page_status = page_data.get("review_status", "pending")
    if page_status == "confirmed":
        return ExtractionReviewPageResponse(
            page_id=str(page_data.get("page_id", page_id)),
            page_number=page.page_number,
            method=page.method,
            classification=page_data.get("classification"),
            original_text=page.text,
            reviewed_text=page_data.get("reviewed_text"),
            final_text_preview=(
                page_data.get("final_text") or page_data.get("reviewed_text")
                or page.text
            )[:80],
            text_changed=bool(page_data.get("text_changed", False)),
            review_status=page_status,
            review_version=current_version,
            reviewed_at=page_data.get("reviewed_at"),
            confirmed_at=page_data.get("confirmed_at"),
            warnings=page.warnings,
            blocks=page_data.get("blocks", []),
            failure=page_data.get("failure"),
            analysis_blocked=bool(page_data.get("analysis_blocked", True)),
        )

    reviewed_text = payload.reviewed_text
    unchanged = bool(payload.unchanged) if payload.unchanged is not None else False

    if not unchanged and reviewed_text is None:
        raise HTTPException(
            status_code=400,
            detail=_error_detail(
                "invalid_review_text",
                "A review text is required unless unchanged is set.",
            ),
        )

    if unchanged:
        reviewed_text = page.text

    if page_data.get("failure"):
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "page_not_reviewable",
                "The page cannot be edited after failure.",
            ),
        )

    _validate_review_text(reviewed_text)

    text_changed = reviewed_text != page.text
    final_text = reviewed_text

    new_version = current_version + 1
    page_data = {
        **page_data,
        "reviewed_text": reviewed_text,
        "text_changed": text_changed,
        "reviewed_at": _to_iso_timestamp(datetime.now(UTC)),
        "review_version": new_version,
        "review_status": "edited" if text_changed else "reviewed",
        "final_text": final_text,
        "confirmed_at": None,
    }

    page.extra_data = page_data
    extraction_metadata = extraction.extra_data or {}
    extraction.extra_data = {
        **extraction_metadata,
        "review_version": int(extraction_metadata.get("review_version", 1)) + 1,
    }

    summary = _build_review_summary(extraction)
    extraction.extra_data["can_confirm"] = _build_can_confirm(extraction, summary)
    extraction.extra_data["blocking_reasons"] = summary["blocking_reasons"]
    extraction.extra_data["review_status"] = summary["extraction_review_status"]

    db.add(extraction)
    db.commit()
    db.refresh(extraction)

    page_data = page.extra_data or {}
    return ExtractionReviewPageResponse(
        page_id=str(page_data.get("page_id", page_id)),
        page_number=page.page_number,
        method=page.method,
        classification=page_data.get("classification"),
        original_text=page.text,
        reviewed_text=page_data.get("reviewed_text"),
        final_text_preview=(page_data.get("final_text") or page.text)[:80],
        text_changed=bool(page_data.get("text_changed", False)),
        review_status=page_data.get("review_status", "pending"),
        review_version=new_version,
        reviewed_at=page_data.get("reviewed_at"),
        confirmed_at=page_data.get("confirmed_at"),
        warnings=page.warnings,
        blocks=page_data.get("blocks", []),
        failure=page_data.get("failure"),
        analysis_blocked=bool(page_data.get("analysis_blocked", True)),
    )


@router.post(
    "/{extraction_id}/confirmation",
    response_model=ExtractionConfirmationResponse,
    responses=ERROR_RESPONSES,
)
def confirm_extraction(
    extraction_id: str,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> ExtractionConfirmationResponse:
    extraction = _get_extraction_with_pages(extraction_id, db)
    request_version = int(
        extraction.extra_data.get("review_version", 1)
        if extraction.extra_data is not None
        else 1
    )
    header_version = _parse_version_value(
        if_match=if_match,
        payload_version=None,
        fallback_error_code="extraction_confirmation_stale",
    )
    if header_version != request_version:
        raise HTTPException(
            status_code=409,
            detail=_error_detail(
                "extraction_confirmation_stale",
                "The extraction review version is stale.",
            ),
        )

    summary = _build_review_summary(extraction)
    if summary["extraction_review_status"] == "confirmed":
        page_snapshot = extraction.extra_data.get("confirmation_snapshot", [])
        if summary["extraction_review_status"] == "confirmed" and page_snapshot:
            return ExtractionConfirmationResponse(
                extraction_id=extraction.id,
                extraction_status=extraction.status,
                review_status="confirmed",
                review_version=request_version,
                snapshot_version=int(extraction.extra_data.get("snapshot_version", 1)),
                confirmed_at=extraction.extra_data["confirmed_at"],
                total_pages=len(extraction.pages),
                confirmed_pages=int(summary["required_pages"]),
                changed_pages=int(summary["edited_pages"]),
                total_text_length=extraction.extra_data.get(
                    "final_total_text_length",
                    0,
                ),
                confirmation_checksum=extraction.extra_data.get(
                    "confirmation_checksum",
                    "",
                ),
                snapshot=[
                    {
                        "page_id": item["page_id"],
                        "page_number": item["page_number"],
                        "final_text": item["final_text"],
                        "text_source": item["text_source"],
                        "text_changed": item["text_changed"],
                        "method": item["method"],
                        "warnings": item["warnings"],
                    }
                    for item in page_snapshot
                ],
            )

    snapshot, confirmed_pages, reviewed_pages, changed_pages = _build_confirmation_snapshot(
        extraction,
    )

    snapshot_timestamp = _to_iso_timestamp(datetime.now(UTC))
    total_text_length = sum(len(item["final_text"]) for item in snapshot)
    checksum = _stable_checksum([item["final_text"] for item in snapshot])

    extraction_snapshot = extraction.extra_data.get("snapshot_version", 0)
    snapshot_version = (
        int(extraction_snapshot) + 1
        if isinstance(extraction_snapshot, int)
        else 1
    )

    for page in sorted(extraction.pages, key=lambda item: item.page_number):
        page_data = page.extra_data or {}
        page_data["review_status"] = "confirmed"
        page_data["confirmed_at"] = snapshot_timestamp
        if page_data.get("review_status") == "edited":
            page_data["final_text"] = page_data.get("reviewed_text")
        else:
            page_data["final_text"] = page.text
        page_data["review_version"] = int(page_data.get("review_version", 1)) + 1
        page.extra_data = page_data

    extraction.extra_data = {
        **(extraction.extra_data or {}),
        "review_status": "confirmed",
        "confirmed_at": snapshot_timestamp,
        "review_version": request_version + 1,
        "confirmation_snapshot": snapshot,
        "snapshot_version": snapshot_version,
        "final_total_text_length": total_text_length,
        "confirmation_checksum": checksum,
        "can_confirm": False,
    }
    extraction.status = "confirmed"
    db.add(extraction)
    db.commit()
    db.refresh(extraction)

    return ExtractionConfirmationResponse(
        extraction_id=extraction.id,
        extraction_status=extraction.status,
        review_status="confirmed",
        review_version=int(extraction.extra_data.get("review_version", 1)),
        snapshot_version=int(extraction.extra_data.get("snapshot_version", 1)),
        confirmed_at=snapshot_timestamp,
        total_pages=len(extraction.pages),
        confirmed_pages=confirmed_pages,
        changed_pages=changed_pages,
        total_text_length=total_text_length,
        confirmation_checksum=checksum,
        snapshot=[
            {
                "page_id": item["page_id"],
                "page_number": item["page_number"],
                "final_text": item["final_text"],
                "text_source": item["text_source"],
                "text_changed": item["text_changed"],
                "method": item["method"],
                "warnings": item["warnings"],
            }
            for item in snapshot
        ],
    )
