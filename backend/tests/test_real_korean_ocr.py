from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.image_ocr import LocalKoreanOcrAdapter, OcrFailure


client = TestClient(app)


def _korean_font_path() -> Path | None:
    candidates = [
        Path(os.getenv("WINGDINGS_FONT", "C:\\Windows\\Fonts\\malgun.ttf")),
        Path("C:\\Windows\\Fonts\\malgun.ttf"),
        Path("C:\\Windows\\Fonts\\malgunbd.ttf"),
        Path("C:\\Windows\\Fonts\\batang.ttc"),
        Path("C:\\Windows\\Fonts\\gulim.ttc"),
        Path("C:\\Windows\\Fonts\\msjh.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _make_ocr_document_bytes(*, ext: str, width: int = 1700, height: int = 1200) -> bytes:
    font_path = _korean_font_path()
    if font_path is None:
        pytest.skip("Korean font is required for integration OCR smoke image.")

    try:
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(str(font_path), size=54)
    except OSError as exc:
        pytest.skip(f"Korean font rendering unavailable: {exc}")

    lines = [
        "Sample Contract OCR",
        "Amount: 3,000,000원",
        "Date: 2026-07-20",
        "Clause 1: Contract period is 3 months.",
        "Deposit: 10,000,원",
    ]

    y = 140
    for line in lines:
        draw.text((110, y), line, fill="black", font=font)
        y += 170

    buffer = BytesIO()
    image.save(buffer, format=ext)
    return buffer.getvalue()


def _rotate_image_bytes(image_bytes: bytes, *, angle: float) -> bytes:
    original = Image.open(BytesIO(image_bytes))
    rotated = original.rotate(angle, expand=True, fillcolor="white")
    buffer = BytesIO()
    rotated.save(buffer, format=original.format or "PNG")
    return buffer.getvalue()


def _post_image(file_name: str, content: bytes, content_type: str):
    return client.post(
        "/extractions/images",
        files=[("files", (file_name, content, content_type))],
    )


def _ensure_local_ocr_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_ADAPTER", "local")
    tesseract_cmd = os.getenv("TESSERACT_CMD", "tesseract")

    if not (shutil.which(tesseract_cmd) or Path(tesseract_cmd).exists()):
        pytest.skip(f"Tesseract binary unavailable: {tesseract_cmd}")

    try:
        _ = LocalKoreanOcrAdapter(language="kor+eng")
    except OcrFailure as exc:
        if exc.code in {"ocr_engine_unavailable", "ocr_model_unavailable"}:
            pytest.skip(f"Local OCR not ready: {exc.code}")
        raise


def test_real_local_ocr_png_jpg_smoke_and_review_confirmation_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_local_ocr_available(monkeypatch)

    png_bytes = _make_ocr_document_bytes(ext="PNG")
    jpg_bytes = _make_ocr_document_bytes(ext="JPEG")

    for extension, filename, content_type, content in [
        ("png", "contract.png", "image/png", png_bytes),
        ("jpeg", "contract.jpg", "image/jpeg", jpg_bytes),
    ]:
        response = _post_image(filename, content, content_type)
        assert response.status_code == 201
        body = response.json()
        extraction_id = body["extraction_id"]

        page = body["pages"][0]
        assert page["source_format"] == extension
        assert len(page["blocks"]) > 0
        assert page["text"]
        assert page["blocks"][0].get("bbox") is not None
        assert page["review_required"] is True
        assert page["analysis_blocked"] is True

        suspected = LocalKoreanOcrAdapter.is_amount_format_suspected(page["text"])
        assert ("ocr_amount_format_suspected" in page["warnings"]) == suspected

        get_response = client.get(f"/extractions/{extraction_id}")
        assert get_response.status_code == 200
        get_body = get_response.json()
        assert get_body["extraction_id"] == extraction_id
        assert get_body["pages"][0]["text"] == page["text"]

        review_response = client.get(f"/extractions/{extraction_id}/review")
        assert review_response.status_code == 200
        review_body = review_response.json()
        review_version = review_body["review_version"]
        assert review_body["review_required"] is True
        assert review_body["required_review_pages"] == len(review_body["pages"]) == 1

        page_id = review_body["pages"][0]["page_id"]
        edited_text = f'{review_body["pages"][0]["original_text"]}\\n[reviewed]'
        patch_response = client.patch(
            f"/extractions/{extraction_id}/pages/{page_id}/review",
            headers={"If-Match": str(review_version)},
            json={"reviewed_text": edited_text},
        )
        assert patch_response.status_code == 200
        page_review = patch_response.json()
        assert page_review["review_status"] in {"reviewed", "edited"}
        assert page_review["review_version"] >= review_version + 1

        confirm_response = client.post(
            f"/extractions/{extraction_id}/confirmation",
            headers={"If-Match": str(review_body["review_version"] + 1)},
        )
        if confirm_response.status_code == 409:
            review_retry = client.get(f"/extractions/{extraction_id}/review")
            assert review_retry.status_code == 200
            retry_version = review_retry.json()["review_version"]
            confirm_response = client.post(
                f"/extractions/{extraction_id}/confirmation",
                headers={"If-Match": str(retry_version)},
            )
        assert confirm_response.status_code == 200
        confirm_body = confirm_response.json()
        assert confirm_body["extraction_status"] == "confirmed"
        assert confirm_body["confirmation_checksum"]


def test_real_local_ocr_mild_skew_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_local_ocr_available(monkeypatch)

    base = _make_ocr_document_bytes(ext="PNG")
    skewed = _rotate_image_bytes(base, angle=3.0)
    response = _post_image("contract_skewed.png", skewed, "image/png")

    assert response.status_code == 201
    body = response.json()
    page = body["pages"][0]
    assert page["review_required"] is True
    assert page["analysis_blocked"] is True
    assert page["text"]
    # Quality warning may be detected as uncertain deskewing.
    assert any(
        code in page["warnings"]
        for code in (
            "deskew_uncertain",
            "perspective_distortion_suspected",
            "image_blurry",
        )
    )
