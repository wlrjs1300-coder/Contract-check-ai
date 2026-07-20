from __future__ import annotations

import time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.api import extractions as extractions_api
from backend.app.db.models import Extraction
from backend.app.main import app
from backend.app.services import extraction_temp_files, image_ocr
from backend.app.services.image_ocr import (
    OcrBlock,
    OcrFailure,
    OcrPageInput,
    OcrPageResult,
)


client = TestClient(app)


class DeterministicOcrAdapter:
    def __init__(
        self,
        *,
        texts: dict[int, str] | None = None,
        confidence: float | None = None,
        block_confidence: float | None = None,
    ) -> None:
        self.texts = texts or {}
        self.confidence = confidence
        self.block_confidence = block_confidence
        self.inputs: list[OcrPageInput] = []

    def recognize(self, page: OcrPageInput) -> OcrPageResult:
        self.inputs.append(page)
        text = self.texts.get(
            page.page_number,
            f"제{page.page_number}조 합성 OCR 계약 문장입니다.",
        )
        return OcrPageResult(
            text=text,
            blocks=(
                OcrBlock(
                    block_index=0,
                    text=text,
                    confidence=self.block_confidence,
                    bbox=(0, 0, page.width, page.height),
                    reading_order=0,
                ),
            ),
            confidence=self.confidence,
        )


@pytest.fixture
def ocr_adapter() -> DeterministicOcrAdapter:
    adapter = DeterministicOcrAdapter()
    app.dependency_overrides[extractions_api.get_ocr_adapter] = lambda: adapter
    yield adapter
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


def _image_bytes(
    image_format: str,
    *,
    size: tuple[int, int] = (1200, 1200),
    mode: str = "RGB",
    color: object = "white",
    orientation: int | None = None,
    png_metadata: PngInfo | None = None,
) -> bytes:
    image = Image.new(mode, size, color)
    output = BytesIO()
    save_options: dict[str, object] = {}
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
        save_options["exif"] = exif
    if png_metadata is not None:
        save_options["pnginfo"] = png_metadata
    image.save(output, format=image_format, **save_options)
    return output.getvalue()


def _animated_png() -> bytes:
    first = Image.new("RGB", (100, 100), "white")
    second = Image.new("RGB", (100, 100), "black")
    output = BytesIO()
    first.save(
        output,
        format="PNG",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return output.getvalue()


def _post_images(items: list[tuple[str, bytes, str]]):
    return client.post(
        "/extractions/images",
        files=[("files", item) for item in items],
    )


def test_adapter_selection_uses_local_ocr_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeLocalAdapter:
        def recognize(self, page: OcrPageInput) -> OcrPageResult:
            del page
            return OcrPageResult(
                text="로컬 OCR 합성 결과",
                blocks=(OcrBlock(0, "로컬 OCR 합성 결과", 0.95, (0, 0, 10, 10), 0),),
                confidence=0.95,
            )

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OCR_ADAPTER", "local_korean")
    monkeypatch.setattr(extractions_api, "LocalKoreanOcrAdapter", lambda: _FakeLocalAdapter())
    adapter = extractions_api.get_ocr_adapter()
    response = adapter.recognize(OcrPageInput(page_number=1, page_id="1", image_bytes=b"", width=10, height=10))

    assert response.text == "로컬 OCR 합성 결과"


def test_synthetic_adapter_is_blocked_outside_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OCR_ADAPTER", "synthetic")

    with pytest.raises(RuntimeError, match="Synthetic OCR adapter is test-only"):
        _ = extractions_api.get_ocr_adapter()


@pytest.mark.parametrize(
    ("filename", "content_type", "image_format", "canonical"),
    [
        ("synthetic.jpg", "image/jpeg", "JPEG", "jpeg"),
        ("synthetic.jpeg", "image/jpeg", "JPEG", "jpeg"),
        ("synthetic.png", "image/png", "PNG", "png"),
    ],
)
def test_accepts_supported_image_formats(
    filename: str,
    content_type: str,
    image_format: str,
    canonical: str,
    ocr_adapter: DeterministicOcrAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(tmp_path / "uploads"))

    response = _post_images(
        [(filename, _image_bytes(image_format), content_type)]
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "image"
    assert body["extraction_method"] == "ocr"
    assert body["total_pages"] == 1
    assert body["completed_pages"] == 1
    assert body["failed_pages"] == 0
    assert body["review_required"] is True
    assert body["analysis_blocked"] is True
    assert body["pages"][0]["page_number"] == 1
    assert body["pages"][0]["page_id"]
    assert body["pages"][0]["source_format"] == canonical
    assert body["pages"][0]["text_length"] == len(body["pages"][0]["text"])
    assert body["pages"][0]["blocks"][0]["confidence"] is None
    get_response = client.get(f"/extractions/{body['extraction_id']}")
    assert get_response.status_code == 200
    assert get_response.json() == body
    assert list((tmp_path / "uploads").iterdir()) == []


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_code"),
    [
        ("synthetic.png", "image/jpeg", "extension_mime_mismatch"),
        ("synthetic.gif", "image/gif", "unsupported_file_type"),
        ("synthetic.webp", "image/webp", "unsupported_file_type"),
        ("synthetic.tiff", "image/tiff", "unsupported_file_type"),
    ],
)
def test_rejects_unsupported_or_mismatched_input(
    filename: str,
    content_type: str,
    expected_code: str,
) -> None:
    response = _post_images([(filename, b"synthetic", content_type)])

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == expected_code
    assert response.json()["detail"]["analysis_blocked"] is True


@pytest.mark.parametrize(
    ("filename", "content_type", "content"),
    [
        ("synthetic.jpg", "image/jpeg", _image_bytes("PNG")),
        ("synthetic.png", "image/png", _image_bytes("JPEG")),
        ("synthetic.png", "image/png", b""),
        ("synthetic.png", "image/png", b"not-an-image"),
        ("synthetic.png", "image/png", _image_bytes("PNG")[:-10]),
        ("synthetic.png", "image/png", _image_bytes("PNG") + b"payload"),
        ("synthetic.jpg", "image/jpeg", _image_bytes("JPEG") + b"payload"),
    ],
    ids=[
        "png-disguised-as-jpeg",
        "jpeg-disguised-as-png",
        "empty",
        "invalid-signature",
        "truncated-png",
        "png-trailing-payload",
        "jpeg-trailing-payload",
    ],
)
def test_rejects_signature_corruption_truncation_and_trailing_payload(
    filename: str,
    content_type: str,
    content: bytes,
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    response = _post_images([(filename, content, content_type)])

    assert response.status_code == 400
    assert response.json()["detail"]["code"] in {
        "invalid_image_signature",
        "corrupted_image",
    }


def test_rejects_animated_png(ocr_adapter: DeterministicOcrAdapter) -> None:
    response = _post_images(
        [("animated.png", _animated_png(), "image/png")]
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unsupported_multiframe_image"


def test_rejects_oversized_metadata(
    monkeypatch: pytest.MonkeyPatch,
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    metadata = PngInfo()
    metadata.add_text("synthetic", "x" * 2_000)
    monkeypatch.setattr(image_ocr, "MAX_METADATA_BYTES", 1_000)

    response = _post_images(
        [
            (
                "metadata.png",
                _image_bytes("PNG", png_metadata=metadata),
                "image/png",
            )
        ]
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "image_metadata_limit_exceeded"
    assert "synthetic" not in response.text


def test_png_alpha_is_composited_on_white_background(
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    response = _post_images(
        [
            (
                "alpha.png",
                _image_bytes("PNG", mode="RGBA", color=(0, 0, 0, 0)),
                "image/png",
            )
        ]
    )

    assert response.status_code == 201
    assert "alpha_background_applied" in response.json()["pages"][0]["warnings"]
    with Image.open(BytesIO(ocr_adapter.inputs[0].image_bytes)) as normalized:
        assert normalized.mode == "RGB"
        assert normalized.getpixel((0, 0)) == (255, 255, 255)
        assert not normalized.info.get("exif")


@pytest.mark.parametrize(
    ("orientation", "expected_size"),
    [(1, (1200, 800)), (3, (1200, 800)), (6, (800, 1200)), (8, (800, 1200))],
)
def test_applies_exif_orientation_and_removes_metadata(
    orientation: int,
    expected_size: tuple[int, int],
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    response = _post_images(
        [
            (
                "oriented.jpg",
                _image_bytes(
                    "JPEG",
                    size=(1200, 800),
                    orientation=orientation,
                ),
                "image/jpeg",
            )
        ]
    )

    assert response.status_code == 201
    page = response.json()["pages"][0]
    assert (page["normalized_width"], page["normalized_height"]) == expected_size
    assert "metadata_removed" in page["warnings"]
    assert ("orientation_normalized" in page["warnings"]) is (orientation != 1)
    assert "GPS" not in response.text


def test_quality_warnings_are_review_only_signals(
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    response = _post_images(
        [
            (
                "small-dark.png",
                _image_bytes("PNG", size=(100, 100), color="black"),
                "image/png",
            )
        ]
    )

    warnings = response.json()["pages"][0]["warnings"]
    assert response.status_code == 201
    assert "low_resolution" in warnings
    assert "possible_blur_or_blank" in warnings
    assert "possible_underexposure" in warnings
    assert "deskew_not_applied" in warnings


@pytest.mark.parametrize(
    ("text", "expected_suspected"),
    [
        ("계약서 금액: 3,000,000원", False),
        ("계약서 금액: 3000,000원", True),
        ("계약서 금액: 1,00,000원", True),
        ("계약서 금액: 10,0000원", True),
        ("계약서 금액: 1,000원", False),
        ("계약서 금액: 3000000원", False),
        ("날짜: 2026-07-20", False),
        ("조항 10-1: 위반 시 손해배상", False),
    ],
)
def test_amount_format_suspected_heuristics(text: str, expected_suspected: bool) -> None:
    assert image_ocr.LocalKoreanOcrAdapter.is_amount_format_suspected(text) is expected_suspected


@pytest.mark.parametrize(
    ("text", "expected_candidates"),
    [
        ("매출액: 3,000원", ["3,000원"]),
        ("혼합: 3000,000원", ["3000,000원"]),
        ("조항: 1,000,원", ["1,000,원"]),
        ("가격: 3000000원", []),
    ],
)
def test_amount_candidate_extraction(
    text: str,
    expected_candidates: list[str],
) -> None:
    assert image_ocr.LocalKoreanOcrAdapter._iter_amount_candidates(text) == expected_candidates


def test_file_and_request_size_limits(
    monkeypatch: pytest.MonkeyPatch,
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    content = _image_bytes("PNG")
    monkeypatch.setattr(extractions_api, "MAX_IMAGE_FILE_BYTES", len(content) - 1)
    response = _post_images([("large.png", content, "image/png")])
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "image_too_large"

    monkeypatch.setattr(extractions_api, "MAX_IMAGE_FILE_BYTES", len(content))
    monkeypatch.setattr(extractions_api, "MAX_REQUEST_SIZE_BYTES", len(content) * 2 - 1)
    response = _post_images(
        [
            ("one.png", content, "image/png"),
            ("two.png", content, "image/png"),
        ]
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_total_size_exceeded"


def test_dimension_page_pixel_and_total_pixel_limits(
    monkeypatch: pytest.MonkeyPatch,
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    content = _image_bytes("PNG", size=(40, 30))
    monkeypatch.setattr(image_ocr, "MAX_IMAGE_DIMENSION", 39)
    response = _post_images([("wide.png", content, "image/png")])
    assert response.json()["detail"]["code"] == "image_dimensions_exceeded"

    monkeypatch.setattr(image_ocr, "MAX_IMAGE_DIMENSION", 100)
    monkeypatch.setattr(image_ocr, "MAX_IMAGE_PIXELS", 1_199)
    response = _post_images([("pixels.png", content, "image/png")])
    assert response.json()["detail"]["code"] == "image_pixel_limit_exceeded"

    monkeypatch.setattr(image_ocr, "MAX_IMAGE_PIXELS", 1_200)
    monkeypatch.setattr(image_ocr, "MAX_REQUEST_PIXELS", 2_399)
    response = _post_images(
        [
            ("one.png", content, "image/png"),
            ("two.png", content, "image/png"),
        ]
    )
    assert response.json()["detail"]["code"] == "request_total_pixel_limit_exceeded"


def test_derived_image_size_limit(
    monkeypatch: pytest.MonkeyPatch,
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    monkeypatch.setattr(image_ocr, "MAX_DERIVED_IMAGE_BYTES", 1)

    response = _post_images(
        [("derived.png", _image_bytes("PNG"), "image/png")]
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "derived_image_limit_exceeded"


def test_image_count_limit(
    monkeypatch: pytest.MonkeyPatch,
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    content = _image_bytes("PNG")
    monkeypatch.setattr(extractions_api, "MAX_IMAGE_COUNT", 1)

    response = _post_images(
        [
            ("one.png", content, "image/png"),
            ("two.png", content, "image/png"),
        ]
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_image_count_exceeded"


def test_ocr_text_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _image_bytes("PNG")
    adapter = DeterministicOcrAdapter(texts={1: "12345", 2: "12345"})
    app.dependency_overrides[extractions_api.get_ocr_adapter] = lambda: adapter
    monkeypatch.setattr(image_ocr, "MAX_PAGE_OCR_CHARACTERS", 4)
    response = _post_images([("one.png", content, "image/png")])
    assert response.json()["detail"]["code"] == "extraction_limit_exceeded"

    monkeypatch.setattr(image_ocr, "MAX_PAGE_OCR_CHARACTERS", 5)
    monkeypatch.setattr(image_ocr, "MAX_TOTAL_OCR_CHARACTERS", 9)
    response = _post_images(
        [
            ("one.png", content, "image/png"),
            ("two.png", content, "image/png"),
        ]
    )
    assert response.json()["detail"]["code"] == "extraction_limit_exceeded"
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


def test_preserves_input_order_filename_order_and_duplicates(
    tmp_path: Path,
) -> None:
    adapter = DeterministicOcrAdapter(
        texts={
            1: "제1조 합성 한글 문장",
            2: "표 합성 값 A B",
            3: "제3조 중복 이미지 문장",
        }
    )
    app.dependency_overrides[extractions_api.get_ocr_adapter] = lambda: adapter
    duplicate = _image_bytes("PNG", color="gray")

    response = _post_images(
        [
            ("z.png", duplicate, "image/png"),
            ("a.png", _image_bytes("PNG", color="white"), "image/png"),
            ("z-copy.png", duplicate, "image/png"),
        ]
    )

    assert response.status_code == 201
    pages = response.json()["pages"]
    assert [page["page_number"] for page in pages] == [1, 2, 3]
    assert [page["text"] for page in pages] == [
        "제1조 합성 한글 문장",
        "표 합성 값 A B",
        "제3조 중복 이미지 문장",
    ]
    assert len({page["page_id"] for page in pages}) == 3
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


@pytest.mark.parametrize("confidence", [None, 0.5])
def test_missing_or_low_confidence_requires_review(
    confidence: float | None,
) -> None:
    adapter = DeterministicOcrAdapter(
        confidence=confidence,
        block_confidence=confidence,
    )
    app.dependency_overrides[extractions_api.get_ocr_adapter] = lambda: adapter

    response = _post_images(
        [("confidence.png", _image_bytes("PNG"), "image/png")]
    )

    warnings = response.json()["pages"][0]["warnings"]
    assert response.status_code == 201
    expected = "ocr_confidence_unavailable" if confidence is None else "ocr_confidence_low"
    assert expected in warnings
    assert response.json()["analysis_blocked"] is True
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


@pytest.mark.parametrize(
    ("adapter", "expected_code"),
    [
        (
            DeterministicOcrAdapter(texts={1: ""}),
            "empty_ocr_result",
        ),
    ],
)
def test_empty_ocr_is_not_success(adapter: object, expected_code: str) -> None:
    app.dependency_overrides[extractions_api.get_ocr_adapter] = lambda: adapter
    response = _post_images(
        [("empty.png", _image_bytes("PNG"), "image/png")]
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == expected_code
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


def test_adapter_exception_and_page_failure_create_no_record(
    db_session: Session,
) -> None:
    class FailingAdapter:
        def recognize(self, page: OcrPageInput) -> OcrPageResult:
            if page.page_number == 2:
                raise OcrFailure
            return OcrPageResult(text="첫 페이지 합성 결과")

    app.dependency_overrides[extractions_api.get_ocr_adapter] = FailingAdapter
    content = _image_bytes("PNG")
    response = _post_images(
        [
            ("one.png", content, "image/png"),
            ("two.png", content, "image/png"),
        ]
    )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "ocr_failed"
    assert response.json()["detail"]["analysis_blocked"] is True
    assert db_session.scalar(select(func.count(Extraction.id))) == 0
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


def test_invalid_block_order_is_not_accepted(db_session: Session) -> None:
    class InvalidBlockAdapter:
        def recognize(self, page: OcrPageInput) -> OcrPageResult:
            return OcrPageResult(
                text="합성 조항 결과",
                blocks=(OcrBlock(2, "합성 조항 결과", 0.9, None, 2),),
            )

    app.dependency_overrides[extractions_api.get_ocr_adapter] = InvalidBlockAdapter
    response = _post_images(
        [("invalid-block.png", _image_bytes("PNG"), "image/png")]
    )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "ocr_failed"
    assert db_session.scalar(select(func.count(Extraction.id))) == 0
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


def test_timeout_is_safe_and_cleans_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    class SlowAdapter:
        def recognize(self, page: OcrPageInput) -> OcrPageResult:
            del page
            time.sleep(0.05)
            return OcrPageResult(text="늦은 합성 결과")

    app.dependency_overrides[extractions_api.get_ocr_adapter] = SlowAdapter
    monkeypatch.setattr(image_ocr, "OCR_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(tmp_path / "uploads"))

    response = _post_images(
        [("slow.png", _image_bytes("PNG"), "image/png")]
    )

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "ocr_timeout"
    assert list((tmp_path / "uploads").iterdir()) == []
    assert db_session.scalar(select(func.count(Extraction.id))) == 0
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


def test_default_adapter_and_synthetic_production_guard() -> None:
    app.dependency_overrides[extractions_api.get_ocr_adapter] = (
        lambda: extractions_api.UnavailableOcrAdapter()
    )

    response = _post_images(
        [("unavailable.png", _image_bytes("PNG"), "image/png")]
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ocr_unavailable"
    assert response.json()["detail"]["analysis_blocked"] is True
    app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)


def test_synthetic_adapter_is_blocked_in_production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OCR_ADAPTER", "synthetic")
    with pytest.raises(RuntimeError):
        _ = extractions_api.get_ocr_adapter()


def test_cleanup_failure_blocks_database_and_exposes_no_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
    ocr_adapter: DeterministicOcrAdapter,
) -> None:
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(tmp_path / "uploads"))
    real_rmtree = extraction_temp_files.shutil.rmtree

    def fail_rmtree(_path: Path) -> None:
        raise PermissionError("synthetic-private-cleanup-detail")

    monkeypatch.setattr(extraction_temp_files.shutil, "rmtree", fail_rmtree)
    response = _post_images(
        [("private-name.png", _image_bytes("PNG"), "image/png")]
    )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "original_cleanup_failed"
    assert response.json()["detail"]["analysis_blocked"] is True
    assert "private-name.png" not in response.text
    assert "synthetic-private-cleanup-detail" not in response.text
    assert db_session.scalar(select(func.count(Extraction.id))) == 0

    monkeypatch.setattr(extraction_temp_files.shutil, "rmtree", real_rmtree)
    for request_path in (tmp_path / "uploads").iterdir():
        real_rmtree(request_path)


def test_openapi_exposes_multi_image_contract() -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/extractions/images"]["post"]
    request_schema = operation["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"]

    assert operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ]["$ref"] == "#/components/schemas/ExtractionResponse"
    assert request_schema["$ref"].startswith("#/components/schemas/Body_")
