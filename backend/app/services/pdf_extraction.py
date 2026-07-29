from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw
from pypdf import PdfReader
from pypdf.errors import PdfReadError


MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGE_COUNT = 100
MAX_PAGE_CHARACTER_COUNT = 200_000
MAX_TOTAL_CHARACTER_COUNT = 2_000_000
MIN_TEXT_CHARACTER_COUNT = 20
MIN_PRINTABLE_RATIO = 0.35
MAX_SUSPICIOUS_RATIO = 0.12
MAX_CONTROL_RATIO = 0.02
PDF_SIGNATURE = b"%PDF-"

DEFAULT_PDF_RENDER_DPI = 150
MAX_PDF_RENDER_PIXELS = 12_000_000
MAX_PDF_RENDER_PAGES = 20
MAX_RENDER_TIMEOUT_SECONDS = 5.0

PDF_PAGE_CLASSIFICATION_DIRECT_USABLE = "direct_usable"
PDF_PAGE_CLASSIFICATION_OCR_REQUIRED = "ocr_required"
PDF_PAGE_CLASSIFICATION_REVIEW_REQUIRED = "review_required"
PDF_PAGE_CLASSIFICATION_BLANK_CANDIDATE = "blank_candidate"
PDF_PAGE_CLASSIFICATION_FAILED = "unsupported_or_failed"


class PDFExtractionFailure:
    code: str
    message: str
    retryable: bool = False


class PdfRenderRequest:
    def __init__(
        self,
        *,
        request_directory,
        source_path: Path,
        page_number: int,
        page_id: str,
    ) -> None:
        self.request_directory = request_directory
        self.source_path = source_path
        self.page_number = page_number
        self.page_id = page_id


@dataclass(frozen=True)
class PdfRenderedPage:
    page_number: int
    page_id: str
    image_bytes: bytes
    width: int
    height: int
    normalized_width: int
    normalized_height: int
    warnings: tuple[str, ...]
    pixel_count: int


class PdfPageRenderer(Protocol):
    def render(self, request: PdfRenderRequest) -> PdfRenderedPage:
        ...


class UnavailablePdfRenderer:
    def render(self, request: PdfRenderRequest) -> PdfRenderedPage:  # noqa: ARG002
        raise PDFExtractionError(
            "pdf_page_renderer_unavailable",
            "PDF page rendering is unavailable.",
            status_code=503,
            retryable=False,
        )


class SyntheticPdfRenderer:
    def __init__(self) -> None:
        if os.getenv("APP_ENV") != "test":
            raise RuntimeError("Synthetic PDF renderer is test-only.")

    def render(self, request: PdfRenderRequest) -> PdfRenderedPage:
        image = Image.new("RGB", (640, 880), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.text((20, 20), f"pdf-page-{request.page_number}:{request.page_id}", fill=(0, 0, 0))
        image_bytes_io = BytesIO()
        image.save(image_bytes_io, format="PNG")

        return PdfRenderedPage(
            page_number=request.page_number,
            page_id=request.page_id,
            image_bytes=image_bytes_io.getvalue(),
            width=640,
            height=880,
            normalized_width=640,
            normalized_height=880,
            warnings=("synthetic_renderer_result",),
            pixel_count=640 * 880,
        )


class PDFExtractionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    extraction_method: str
    warnings: tuple[str, ...]
    classification: str
    review_required: bool
    page_id: str


@dataclass(frozen=True)
class ExtractedPDF:
    pages: tuple[ExtractedPage, ...]
    warnings: tuple[str, ...]


def validate_pdf_signature(path: Path) -> None:
    with path.open("rb") as source:
        signature = source.read(len(PDF_SIGNATURE))

    if signature != PDF_SIGNATURE:
        raise PDFExtractionError(
            "file_type_mismatch",
            "The uploaded file does not match the PDF format.",
        )


def _analyze_text_quality(text: str) -> tuple[str, tuple[str, ...], bool]:
    if not text:
        return (
            PDF_PAGE_CLASSIFICATION_BLANK_CANDIDATE,
            ("empty_page_text", "ocr_required"),
            True,
        )

    visible_characters = [character for character in text if not character.isspace()]

    if not visible_characters:
        return (
            PDF_PAGE_CLASSIFICATION_BLANK_CANDIDATE,
            ("empty_page_text", "ocr_required"),
            True,
        )

    printable_characters = [
        character for character in visible_characters if character.isprintable()
    ]
    suspicious_characters = [
        character
        for character in visible_characters
        if character == "\ufffd" or not character.isprintable()
    ]
    control_characters = [
        character
        for character in visible_characters
        if character in {"\x00", "\x1b", "\x7f"}
    ]

    warnings: list[str] = []

    printable_ratio = len(printable_characters) / len(visible_characters)
    suspicious_ratio = (
        len(suspicious_characters) / len(visible_characters)
        if visible_characters
        else 1.0
    )
    control_ratio = len(control_characters) / len(visible_characters)

    if (
        len(visible_characters) < MIN_TEXT_CHARACTER_COUNT
        or printable_ratio < MIN_PRINTABLE_RATIO
        or suspicious_ratio > MAX_SUSPICIOUS_RATIO
        or control_ratio > MAX_CONTROL_RATIO
    ):
        warnings.extend(("text_layer_low_quality", "ocr_required"))
        return (
            PDF_PAGE_CLASSIFICATION_OCR_REQUIRED,
            tuple(dict.fromkeys(warnings)),
            True,
        )

    if warnings:
        return (
            PDF_PAGE_CLASSIFICATION_REVIEW_REQUIRED,
            tuple(dict.fromkeys(warnings + ["review_required"])),
            True,
        )

    return (PDF_PAGE_CLASSIFICATION_DIRECT_USABLE, tuple(warnings), False)


def extract_text_pdf(path: Path) -> ExtractedPDF:
    validate_pdf_signature(path)

    try:
        reader = PdfReader(path, strict=True)

        if reader.is_encrypted:
            raise PDFExtractionError(
                "encrypted_pdf",
                "Encrypted PDF files are not supported.",
            )

        page_count = len(reader.pages)
    except PDFExtractionError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise PDFExtractionError(
            "corrupt_document",
            "The PDF file is damaged or cannot be read.",
        ) from exc
    except Exception as exc:
        raise PDFExtractionError(
            "extraction_failed",
            "The PDF extraction could not be completed.",
            status_code=500,
            retryable=True,
        ) from exc

    if page_count < 1:
        raise PDFExtractionError(
            "empty_document",
            "The PDF file does not contain any pages.",
        )

    if page_count > MAX_PDF_PAGE_COUNT:
        raise PDFExtractionError(
            "page_limit_exceeded",
            "The PDF file exceeds the 100 page limit.",
            status_code=422,
        )

    extracted_pages: list[ExtractedPage] = []
    total_character_count = 0

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise PDFExtractionError(
                "extraction_failed",
                "The PDF text could not be extracted.",
                status_code=500,
                retryable=True,
            ) from exc

        if len(text) > MAX_PAGE_CHARACTER_COUNT:
            raise PDFExtractionError(
                "text_limit_exceeded",
                "A PDF page exceeds the extracted text limit.",
                status_code=422,
            )

        total_character_count += len(text)

        if total_character_count > MAX_TOTAL_CHARACTER_COUNT:
            raise PDFExtractionError(
                "text_limit_exceeded",
                "The PDF file exceeds the extracted text limit.",
                status_code=422,
            )

        classification, page_warnings, review_required = _analyze_text_quality(text)
        extracted_pages.append(
            ExtractedPage(
                page_number=page_number,
                text=text,
                extraction_method="direct",
                classification=classification,
                warnings=page_warnings,
                review_required=review_required,
                page_id=f"page-{page_number}",
            )
        )

    warnings: list[str] = []

    if any("empty_page_text" in page.warnings for page in extracted_pages):
        warnings.append("empty_pages_detected")

    if any("ocr_required" in page.warnings for page in extracted_pages):
        warnings.append("ocr_required_pages")

    return ExtractedPDF(
        pages=tuple(extracted_pages),
        warnings=tuple(warnings),
    )
