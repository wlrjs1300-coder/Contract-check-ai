from __future__ import annotations

import io
import os
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError


MAX_IMAGE_FILE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_SIZE_BYTES = 30 * 1024 * 1024
MAX_IMAGE_COUNT = 10
MAX_IMAGE_DIMENSION = 10_000
MAX_IMAGE_PIXELS = 25_000_000
MAX_REQUEST_PIXELS = 100_000_000
MAX_PAGE_OCR_CHARACTERS = 200_000
MAX_TOTAL_OCR_CHARACTERS = 1_000_000
MAX_DERIVED_IMAGE_BYTES = 20 * 1024 * 1024
MAX_METADATA_BYTES = 256 * 1024
OCR_TIMEOUT_SECONDS = 10.0
MIN_RECOMMENDED_WIDTH = 1_000
MIN_RECOMMENDED_HEIGHT = 1_000
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
SUPPORTED_EXTENSIONS = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png"}
SUPPORTED_CONTENT_TYPES = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
}


class ImageExtractionError(Exception):
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


class OcrFailure(Exception):
    def __init__(self, code: str = "ocr_failed") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OcrPageInput:
    page_number: int
    page_id: str
    image_bytes: bytes
    width: int
    height: int


@dataclass(frozen=True)
class OcrBlock:
    block_index: int
    text: str
    confidence: float | None
    bbox: tuple[int, int, int, int] | None
    reading_order: int


@dataclass(frozen=True)
class OcrPageResult:
    text: str
    blocks: tuple[OcrBlock, ...] = ()
    confidence: float | None = None
    warnings: tuple[str, ...] = ()


class OcrAdapter(Protocol):
    def recognize(self, page: OcrPageInput) -> OcrPageResult:
        ...


class UnavailableOcrAdapter:
    def recognize(self, page: OcrPageInput) -> OcrPageResult:
        del page
        raise OcrFailure("ocr_unavailable")


class SyntheticOcrAdapter:
    def __init__(self) -> None:
        if os.getenv("APP_ENV") != "test":
            raise RuntimeError("The synthetic OCR adapter is test-only.")

    def recognize(self, page: OcrPageInput) -> OcrPageResult:
        text = f"합성 OCR 페이지 {page.page_number}"
        return OcrPageResult(
            text=text,
            blocks=(OcrBlock(0, text, None, None, 0),),
            confidence=None,
            warnings=("synthetic_ocr_result",),
        )


@dataclass(frozen=True)
class PreparedImage:
    page_number: int
    page_id: str
    canonical_format: str
    normalized_path: Path
    normalized_width: int
    normalized_height: int
    pixel_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ExtractedImagePage:
    page_number: int
    page_id: str
    normalized_width: int
    normalized_height: int
    text: str
    blocks: tuple[OcrBlock, ...]
    warnings: tuple[str, ...]
    review_required: bool
    analysis_blocked: bool


@dataclass(frozen=True)
class ExtractedImages:
    pages: tuple[ExtractedImagePage, ...]
    warnings: tuple[str, ...]
    total_text_length: int
    review_required: bool
    analysis_blocked: bool


def canonical_format_from_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        return SUPPORTED_EXTENSIONS[suffix]
    except KeyError as exc:
        raise ImageExtractionError(
            "unsupported_file_type",
            "Only JPG, JPEG, and PNG image files are supported.",
        ) from exc


def validate_content_type(content_type: str | None, expected: str) -> None:
    actual = SUPPORTED_CONTENT_TYPES.get((content_type or "").lower())
    if actual != expected:
        raise ImageExtractionError(
            "extension_mime_mismatch",
            "The image extension and content type do not match.",
        )


def _signature_format(data: bytes) -> str:
    if data.startswith(PNG_SIGNATURE):
        return "png"
    if data.startswith(JPEG_SIGNATURE):
        return "jpeg"
    raise ImageExtractionError(
        "invalid_image_signature",
        "The uploaded file does not have a supported image signature.",
    )


def _validate_png_end(data: bytes) -> None:
    offset = len(PNG_SIGNATURE)
    found_end = False

    while offset < len(data):
        if offset + 12 > len(data):
            break
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            break
        offset = chunk_end
        if chunk_type == b"IEND":
            found_end = True
            break

    if not found_end or offset != len(data):
        raise ImageExtractionError(
            "corrupted_image",
            "The PNG image is incomplete or contains trailing data.",
        )


def _validate_no_trailing_payload(data: bytes, canonical_format: str) -> None:
    if canonical_format == "png":
        _validate_png_end(data)
        return
    if not data.endswith(b"\xff\xd9"):
        raise ImageExtractionError(
            "corrupted_image",
            "The JPEG image is incomplete or contains trailing data.",
        )


def _metadata_size(image: Image.Image) -> int:
    total = 0
    for key, value in image.info.items():
        total += len(str(key).encode("utf-8"))
        if isinstance(value, bytes):
            total += len(value)
        else:
            total += len(str(value).encode("utf-8"))
    try:
        total += len(image.getexif().tobytes())
    except (AttributeError, OSError, ValueError):
        pass
    return total


def _quality_warnings(image: Image.Image) -> list[str]:
    result: list[str] = []
    width, height = image.size
    if width < MIN_RECOMMENDED_WIDTH or height < MIN_RECOMMENDED_HEIGHT:
        result.append("low_resolution")

    sample = ImageOps.grayscale(image)
    sample.thumbnail((512, 512))
    brightness = ImageStat.Stat(sample).mean[0]
    edge_variance = ImageStat.Stat(sample.filter(ImageFilter.FIND_EDGES)).var[0]
    if edge_variance < 20:
        result.append("possible_blur_or_blank")
    if brightness < 30:
        result.append("possible_underexposure")
    elif brightness > 225:
        result.append("possible_overexposure")
    return result


def prepare_image(
    source_path: Path,
    *,
    expected_format: str,
    page_number: int,
) -> PreparedImage:
    data = source_path.read_bytes()
    actual_signature = _signature_format(data)
    if actual_signature != expected_format:
        raise ImageExtractionError(
            "invalid_image_signature",
            "The image extension and signature do not match.",
        )
    _validate_no_trailing_payload(data, actual_signature)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                if (getattr(opened, "n_frames", 1) != 1 or getattr(opened, "is_animated", False)):
                    raise ImageExtractionError(
                        "unsupported_multiframe_image",
                        "Multi-frame and animated images are not supported.",
                    )
                decoder_format = (opened.format or "").lower()
                if decoder_format == "jpg":
                    decoder_format = "jpeg"
                if decoder_format != expected_format:
                    raise ImageExtractionError(
                        "invalid_image_signature",
                        "The image decoder format does not match the upload.",
                    )
                if _metadata_size(opened) > MAX_METADATA_BYTES:
                    raise ImageExtractionError(
                        "image_metadata_limit_exceeded",
                        "The image metadata exceeds the allowed limit.",
                        status_code=413,
                    )
                width, height = opened.size
                if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                    raise ImageExtractionError(
                        "image_dimensions_exceeded",
                        "The image dimensions exceed the allowed limit.",
                        status_code=413,
                    )
                if width * height > MAX_IMAGE_PIXELS:
                    raise ImageExtractionError(
                        "image_pixel_limit_exceeded",
                        "The image pixel count exceeds the allowed limit.",
                        status_code=413,
                    )
                opened.load()
                had_metadata = bool(opened.info) or bool(opened.getexif())
                orientation = opened.getexif().get(274, 1)
                normalized = ImageOps.exif_transpose(opened)
                normalized.load()
                normalized_width, normalized_height = normalized.size
                page_warnings = _quality_warnings(normalized)
                if orientation != 1:
                    page_warnings.append("orientation_normalized")
                if had_metadata:
                    page_warnings.append("metadata_removed")
                if "A" in normalized.getbands():
                    background = Image.new("RGB", normalized.size, "white")
                    background.paste(normalized, mask=normalized.getchannel("A"))
                    normalized = background
                    page_warnings.append("alpha_background_applied")
                else:
                    normalized = normalized.convert("RGB")
                page_warnings.append("deskew_not_applied")

                normalized_path = source_path.with_name(f"{uuid4()}.normalized.png")
                normalized.save(normalized_path, format="PNG", optimize=True)
    except ImageExtractionError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise ImageExtractionError(
            "corrupted_image",
            "The image could not be decoded completely.",
        ) from exc

    if normalized_path.stat().st_size > MAX_DERIVED_IMAGE_BYTES:
        raise ImageExtractionError(
            "derived_image_limit_exceeded",
            "The normalized image exceeds the processing limit.",
            status_code=413,
        )

    return PreparedImage(
        page_number=page_number,
        page_id=f"page-{uuid4()}",
        canonical_format=expected_format,
        normalized_path=normalized_path,
        normalized_width=normalized_width,
        normalized_height=normalized_height,
        pixel_count=normalized_width * normalized_height,
        warnings=tuple(dict.fromkeys(page_warnings)),
    )


def _run_adapter(
    adapter: OcrAdapter,
    page_input: OcrPageInput,
    *,
    timeout_seconds: float,
) -> OcrPageResult:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-page")
    future = executor.submit(adapter.recognize, page_input)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise ImageExtractionError(
            "ocr_timeout",
            "The image text extraction timed out.",
            status_code=504,
            retryable=True,
        ) from exc
    except OcrFailure as exc:
        code = exc.code if exc.code == "ocr_unavailable" else "ocr_failed"
        raise ImageExtractionError(
            code,
            "The image text extraction could not be completed.",
            status_code=503 if code == "ocr_unavailable" else 500,
            retryable=True,
        ) from exc
    except Exception as exc:
        raise ImageExtractionError(
            "ocr_failed",
            "The image text extraction could not be completed.",
            status_code=500,
            retryable=True,
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _validate_ocr_result(
    result: OcrPageResult,
    prepared: PreparedImage,
) -> None:
    if result.confidence is not None and not 0 <= result.confidence <= 1:
        raise ImageExtractionError(
            "ocr_failed",
            "The image text extraction returned an invalid result.",
            status_code=500,
        )

    for expected_index, block in enumerate(result.blocks):
        if (
            block.block_index != expected_index
            or block.reading_order != expected_index
            or not block.text.strip()
            or (block.confidence is not None and not 0 <= block.confidence <= 1)
        ):
            raise ImageExtractionError(
                "ocr_failed",
                "The image text extraction returned an invalid result.",
                status_code=500,
            )
        if block.bbox is not None:
            left, top, right, bottom = block.bbox
            if not (
                0 <= left < right <= prepared.normalized_width
                and 0 <= top < bottom <= prepared.normalized_height
            ):
                raise ImageExtractionError(
                    "ocr_failed",
                    "The image text extraction returned an invalid result.",
                    status_code=500,
                )


def extract_images(
    prepared_images: list[PreparedImage],
    adapter: OcrAdapter,
    *,
    timeout_seconds: float | None = None,
) -> ExtractedImages:
    effective_timeout = (
        OCR_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    )
    if sum(page.pixel_count for page in prepared_images) > MAX_REQUEST_PIXELS:
        raise ImageExtractionError(
            "request_total_pixel_limit_exceeded",
            "The request pixel count exceeds the allowed limit.",
            status_code=413,
        )

    extracted_pages: list[ExtractedImagePage] = []
    total_characters = 0
    for prepared in prepared_images:
        image_bytes = prepared.normalized_path.read_bytes()
        result = _run_adapter(
            adapter,
            OcrPageInput(
                page_number=prepared.page_number,
                page_id=prepared.page_id,
                image_bytes=image_bytes,
                width=prepared.normalized_width,
                height=prepared.normalized_height,
            ),
            timeout_seconds=effective_timeout,
        )
        if not result.text.strip():
            raise ImageExtractionError(
                "empty_ocr_result",
                "No text could be extracted from an image.",
                status_code=422,
            )
        _validate_ocr_result(result, prepared)
        if len(result.text) > MAX_PAGE_OCR_CHARACTERS:
            raise ImageExtractionError(
                "extraction_limit_exceeded",
                "The extracted page text exceeds the allowed limit.",
                status_code=422,
            )
        total_characters += len(result.text)
        if total_characters > MAX_TOTAL_OCR_CHARACTERS:
            raise ImageExtractionError(
                "extraction_limit_exceeded",
                "The extracted document text exceeds the allowed limit.",
                status_code=422,
            )

        page_warnings = list(prepared.warnings)
        page_warnings.extend(result.warnings)
        if result.confidence is None:
            page_warnings.append("ocr_confidence_unavailable")
        elif result.confidence < 0.8:
            page_warnings.append("ocr_confidence_low")
        if len(result.text.strip()) < 20:
            page_warnings.append("ocr_text_short")
        if any(block.confidence is not None and block.confidence < 0.8 for block in result.blocks):
            page_warnings.append("ocr_block_confidence_low")

        extracted_pages.append(
            ExtractedImagePage(
                page_number=prepared.page_number,
                page_id=prepared.page_id,
                normalized_width=prepared.normalized_width,
                normalized_height=prepared.normalized_height,
                text=result.text,
                blocks=result.blocks,
                warnings=tuple(dict.fromkeys(page_warnings)),
                review_required=True,
                analysis_blocked=True,
            )
        )

    if [page.page_number for page in extracted_pages] != list(range(1, len(prepared_images) + 1)):
        raise ImageExtractionError(
            "ocr_failed",
            "The image page sequence could not be verified.",
            status_code=500,
        )

    all_warnings = tuple(
        dict.fromkeys(
            warning
            for page in extracted_pages
            for warning in page.warnings
        )
    )
    return ExtractedImages(
        pages=tuple(extracted_pages),
        warnings=all_warnings,
        total_text_length=total_characters,
        review_required=True,
        analysis_blocked=True,
    )
