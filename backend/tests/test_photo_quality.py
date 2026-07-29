from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from backend.app.services.image_ocr import _assess_image_quality


def _base_contract_like_image(*, width: int, height: int, font_size: int = 60) -> Image.Image:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:\\Windows\\Fonts\\malgun.ttf", font_size)
    except OSError:  # pragma: no cover - platform dependent
        font = ImageFont.load_default()

    draw.rectangle((60, 60, width - 60, height - 60), outline="black", width=4)
    y = 120
    for _ in range(7):
        draw.text((140, y), "계약 조항 예시 텍스트 12345", fill="black", font=font)
        y += max(40, font_size + 22)
    return image


def _image_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_quality_assessment_clean_profile_has_no_readability_block() -> None:
    image = _base_contract_like_image(width=1600, height=1200)
    warnings = _assess_image_quality(image)
    assert "image_unreadable" not in warnings
    assert "image_quality_too_low" not in warnings
    assert "image_blurry" not in warnings


@pytest.mark.parametrize(
    ("radius", "expected_warning"),
    [(4.5, "image_quality_too_low"), (8.0, "image_quality_too_low")],
)
def test_quality_assessment_blur_detection(radius: float, expected_warning: str) -> None:
    image = _base_contract_like_image(width=1600, height=1200)
    blurred = image.filter(ImageFilter.GaussianBlur(radius=radius))
    warnings = _assess_image_quality(blurred)
    assert expected_warning in warnings


def test_quality_assessment_size_and_bounds() -> None:
    image = _base_contract_like_image(width=800, height=700)
    warnings = _assess_image_quality(image)
    assert "low_resolution" in warnings
    assert "image_resolution_low" in warnings


def test_quality_assessment_skew_suspected() -> None:
    image = _base_contract_like_image(width=1600, height=1200)
    rotated = image.rotate(4, expand=False, fillcolor="white")
    warnings = _assess_image_quality(rotated)
    assert "deskew_uncertain" in warnings or "perspective_distortion_suspected" in warnings


def test_quality_assessment_background_and_crop_signal() -> None:
    image = _base_contract_like_image(width=1600, height=1200)
    rotated = image.rotate(0)
    warnings = _assess_image_quality(rotated)
    assert ("background_included" in warnings) or ("document_boundary_uncertain" in warnings)


def test_skew_signal_removed_when_no_angle() -> None:
    image = _base_contract_like_image(width=1600, height=1200)
    warnings = _assess_image_quality(image)
    assert "deskew_uncertain" not in warnings
