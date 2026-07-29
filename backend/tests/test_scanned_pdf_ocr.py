from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from backend.app.api import extractions as extractions_api
from backend.app.main import app
from backend.app.services.pdf_extraction import PdfRenderRequest, PdfRenderedPage
from backend.app.services.image_ocr import (
    ImageExtractionError,
    OcrBlock,
    OcrFailure,
    OcrPageResult,
)

from backend.tests.test_pdf_extraction import _blank_pdf, _synthetic_text_pdf


client = TestClient(app)


@pytest.fixture(autouse=True)
def force_test_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")


def _post_pdf(content: bytes):
    return client.post(
        "/extractions",
        files={"file": ("synthetic.pdf", content, "application/pdf")},
    )


class DeterministicRenderer:
    def __init__(self, *, page_fail: set[int] | None = None) -> None:
        self.page_fail = page_fail or set()
        self.calls: list[tuple[int, str]] = []

    def render(self, request: PdfRenderRequest) -> PdfRenderedPage:
        if request.page_number in self.page_fail:
            raise ImageExtractionError(
                "pdf_page_render_failed",
                "Synthetic renderer failure.",
                status_code=500,
            )
        self.calls.append((request.page_number, request.page_id))
        return PdfRenderedPage(
            page_number=request.page_number,
            page_id=request.page_id,
            image_bytes=b"synthetic",
            width=1024,
            height=1024,
            normalized_width=1024,
            normalized_height=1024,
            warnings=("deterministic_render",),
            pixel_count=1024 * 1024,
        )


class OcrFailAdapter:
    def __init__(self, *, fail_pages: set[int] | None = None) -> None:
        self.calls: list[tuple[int, str]] = []
        self.fail_pages = fail_pages or set()

    def recognize(self, page) -> object:  # noqa: ANN001
        self.calls.append((page.page_number, page.page_id))
        if page.page_number in self.fail_pages:
            raise OcrFailure("ocr_unavailable")
        text = f"synthetic OCR page {page.page_number}"
        return OcrPageResult(
            text=text,
            blocks=(OcrBlock(0, text, None, None, 0),),
            confidence=None,
            warnings=(),
        )


def test_scanned_only_pdf_routes_through_synthetic_renderer_and_ocr() -> None:
    response = _post_pdf(_blank_pdf(page_count=2))

    assert response.status_code == 201
    body = response.json()
    assert body["extraction_method"] == "ocr"
    assert body["warnings"] == ["empty_pages_detected", "ocr_required_pages"]
    assert [page["extraction_method"] for page in body["pages"]] == ["ocr", "ocr"]
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert [page["page_id"] for page in body["pages"]] == ["page-1", "page-2"]
    assert len(body["pages"][0]["blocks"]) == 1
    assert body["pages"][0]["blocks"][0]["text"].startswith("합성 OCR 페이지")
    assert body["pages"][0]["analysis_blocked"] is True
    assert body["pages"][0]["requires_user_review"] is True


def test_mixed_pdf_preserves_sequence_and_method() -> None:
    content = _synthetic_text_pdf(
        [
            "첫 번째 페이지는 직접 분석이 가능한 긴 조항 텍스트입니다.",
            "",
            "짧은 문장",
        ]
    )
    response = _post_pdf(content)

    assert response.status_code == 201
    body = response.json()
    assert body["extraction_method"] == "mixed"
    assert [p["page_number"] for p in body["pages"]] == [1, 2, 3]
    assert [p["extraction_method"] for p in body["pages"]] == ["direct", "ocr", "ocr"]
    assert [p["analysis_blocked"] for p in body["pages"]] == [False, True, True]
    assert body["warnings"] == ["empty_pages_detected", "ocr_required_pages"]


def test_partial_ocr_failure_keeps_failed_page_and_stops_cleanly() -> None:
    renderer = DeterministicRenderer(page_fail={2})
    adapter = OcrFailAdapter(fail_pages={2})
    app.dependency_overrides[extractions_api.get_pdf_renderer] = lambda: renderer
    app.dependency_overrides[extractions_api.get_ocr_adapter] = lambda: adapter
    try:
        response = _post_pdf(_blank_pdf(page_count=2))
    finally:
        app.dependency_overrides.pop(extractions_api.get_pdf_renderer, None)
        app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)

    assert response.status_code == 201
    body = response.json()
    assert body["completed_pages"] == 1
    assert body["failed_pages"] == 1
    assert body["pages"][0]["page_number"] == 1
    assert body["pages"][1]["page_number"] == 2
    assert body["pages"][1]["failure"] == "pdf_page_render_failed"
    assert body["pages"][1]["analysis_blocked"] is True
    assert body["pages"][1]["requires_user_review"] is True


def test_cleanup_is_attempted_for_mixed_failure_and_no_leftover_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXTRACTION_TEMP_ROOT", str(tmp_path / "uploads"))

    renderer = DeterministicRenderer(page_fail={1})
    adapter = OcrFailAdapter()
    app.dependency_overrides[extractions_api.get_pdf_renderer] = lambda: renderer
    app.dependency_overrides[extractions_api.get_ocr_adapter] = lambda: adapter
    try:
        response = _post_pdf(_blank_pdf(page_count=1))
    finally:
        app.dependency_overrides.pop(extractions_api.get_pdf_renderer, None)
        app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)

    assert response.status_code == 201
    assert response.json()["failed_pages"] == 1
    assert list((tmp_path / "uploads").iterdir()) == []


def test_renderer_unavailable_production_path_is_blocked() -> None:
    with pytest.MonkeyPatch().context() as monkeypatch:
        monkeypatch.setenv("APP_ENV", "production")
        response = _post_pdf(_blank_pdf())

    assert response.status_code == 201
    body = response.json()
    assert body["pages"][0]["failure"] == "pdf_page_renderer_unavailable"
    assert body["pages"][0]["analysis_blocked"] is True
    assert body["review_required"] is True
    assert body["analysis_blocked"] is True


def test_ocr_unavailable_production_path_is_distinguishable() -> None:
    renderer = DeterministicRenderer()

    class ProductionLikeUnavailableOcr:
        def recognize(self, page):  # noqa: ANN001
            del page
            raise OcrFailure("ocr_unavailable")

    with pytest.MonkeyPatch().context() as monkeypatch:
        monkeypatch.setenv("APP_ENV", "production")
        app.dependency_overrides[extractions_api.get_pdf_renderer] = lambda: renderer
        app.dependency_overrides[extractions_api.get_ocr_adapter] = (
            lambda: ProductionLikeUnavailableOcr()
        )
        try:
            response = _post_pdf(_blank_pdf())
        finally:
            app.dependency_overrides.pop(extractions_api.get_pdf_renderer, None)
            app.dependency_overrides.pop(extractions_api.get_ocr_adapter, None)

    assert response.status_code == 201
    body = response.json()
    assert body["pages"][0]["failure"] == "ocr_unavailable"
    assert body["analysis_blocked"] is True
