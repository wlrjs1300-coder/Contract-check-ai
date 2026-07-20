from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGE_COUNT = 100
MAX_PAGE_CHARACTER_COUNT = 200_000
MAX_TOTAL_CHARACTER_COUNT = 2_000_000
MIN_TEXT_CHARACTER_COUNT = 20
PDF_SIGNATURE = b"%PDF-"


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
    warnings: tuple[str, ...]


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


def _page_warnings(text: str) -> tuple[str, ...]:
    if not text.strip():
        return ("empty_page_text", "ocr_required")

    visible_characters = [character for character in text if not character.isspace()]
    suspicious_characters = [
        character
        for character in visible_characters
        if character == "\ufffd" or not character.isprintable()
    ]
    warnings: list[str] = []

    if (
        len(visible_characters) < MIN_TEXT_CHARACTER_COUNT
        or (
            suspicious_characters
            and len(suspicious_characters) / len(visible_characters) > 0.05
        )
    ):
        warnings.extend(("text_layer_low_quality", "ocr_required"))

    return tuple(warnings)


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

        extracted_pages.append(
            ExtractedPage(
                page_number=page_number,
                text=text,
                warnings=_page_warnings(text),
            )
        )

    if not any(page.text.strip() for page in extracted_pages):
        raise PDFExtractionError(
            "extraction_empty",
            "No text layer was found in the PDF file.",
            status_code=422,
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
