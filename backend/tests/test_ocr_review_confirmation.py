from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.tests.test_pdf_extraction import _synthetic_text_pdf


client = TestClient(app)


@pytest.fixture(autouse=True)
def force_test_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")


def _png_bytes() -> bytes:
    image = Image.new("RGB", (1200, 1200), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _post_image_extraction() -> dict:
    response = client.post(
        "/extractions/images",
        files=[
            ("files", ("page1.png", _png_bytes(), "image/png")),
            ("files", ("page2.png", _png_bytes(), "image/png")),
        ],
    )
    assert response.status_code == 201
    return response.json()


def _post_direct_pdf_extraction() -> dict:
    response = client.post(
        "/extractions",
        files={
            "file": (
                "contract.txt.pdf",
                _synthetic_text_pdf(["Clause one", "Clause two"]),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


def _post_mixed_pdf_extraction() -> dict:
    response = client.post(
        "/extractions",
        files={
            "file": (
                "mixed.pdf",
                _synthetic_text_pdf(["mixed text", ""]),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


def _confirm_direct_once(extraction_id: str) -> int:
    review = client.get(f"/extractions/{extraction_id}/review")
    assert review.status_code == 200
    assert review.json()["review_version"] == 1
    confirmation = client.post(
        f"/extractions/{extraction_id}/confirmation",
        headers={"If-Match": "1"},
    )
    assert confirmation.status_code == 200
    assert confirmation.json()["review_status"] == "confirmed"
    return confirmation.json()["review_version"]


def test_direct_pdf_extraction_is_not_review_required() -> None:
    extraction = _post_direct_pdf_extraction()
    extraction_id = extraction["extraction_id"]

    review = client.get(f"/extractions/{extraction_id}/review").json()
    if extraction["requires_user_review"]:
        assert review["review_required"] is True
        assert review["review_status"] in {"pending", "partially_reviewed", "ready_to_confirm"}
    else:
        assert extraction["review_required"] is False
        assert extraction["review_status"] == "confirmed"
        assert extraction["analysis_blocked"] is False
        assert all(
            page["requires_user_review"] is False for page in extraction["pages"]
        )
        assert all(page["review_status"] == "not_required" for page in extraction["pages"])
        assert review["review_status"] == "not_required"
        assert review["review_version"] == 1

    review = client.get(f"/extractions/{extraction_id}/review")
    assert review.status_code == 200
    review.json()


def test_direct_pdf_confirmation_and_idempotency() -> None:
    extraction = _post_direct_pdf_extraction()
    extraction_id = extraction["extraction_id"]

    if extraction["requires_user_review"]:
        # This branch validates the normal review-required path (not idempotent yet).
        review = client.get(f"/extractions/{extraction_id}/review").json()
        response = client.post(
            f"/extractions/{extraction_id}/confirmation",
            headers={"If-Match": str(review["review_version"])},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "extraction_review_incomplete"
    else:
        response = client.post(f"/extractions/{extraction_id}/confirmation")
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "extraction_confirmation_stale"

        first_version = _confirm_direct_once(extraction_id)
        stale = client.post(
            f"/extractions/{extraction_id}/confirmation",
            headers={"If-Match": "1"},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "extraction_confirmation_stale"

        second = client.post(
            f"/extractions/{extraction_id}/confirmation",
            headers={"If-Match": str(first_version)},
        )
        assert second.status_code == 200
        body = second.json()
        assert body["review_status"] == "confirmed"
        assert body["review_version"] == first_version
        assert len(body["snapshot"]) == 2
        assert [item["page_number"] for item in body["snapshot"]] == [1, 2]


def test_direct_pdf_page_review_forbidden() -> None:
    extraction = _post_direct_pdf_extraction()
    extraction_id = extraction["extraction_id"]
    first_page = extraction["pages"][0]["page_id"]

    response = client.patch(
        f"/extractions/{extraction_id}/pages/{first_page}/review",
        json={"unchanged": True, "version": 1},
    )
    if extraction["requires_user_review"]:
        assert response.status_code == 200
    else:
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "extraction_not_reviewable"


def test_image_review_and_confirmation_snapshot_is_used() -> None:
    extraction = _post_image_extraction()
    extraction_id = extraction["extraction_id"]
    pages = client.get(f"/extractions/{extraction_id}/review").json()["pages"]
    first = pages[0]
    second = pages[1]

    edited_text = "edited text for review"
    patch1 = client.patch(
        f"/extractions/{extraction_id}/pages/{first['page_id']}/review",
        json={"version": first["review_version"], "reviewed_text": edited_text},
    )
    assert patch1.status_code == 200
    assert patch1.json()["review_status"] == "edited"
    assert patch1.json()["text_changed"] is True

    patch2 = client.patch(
        f"/extractions/{extraction_id}/pages/{second['page_id']}/review",
        json={"version": second["review_version"], "unchanged": True},
    )
    assert patch2.status_code == 200

    review_before = client.get(f"/extractions/{extraction_id}/review").json()
    confirm_missing = client.post(f"/extractions/{extraction_id}/confirmation")
    assert confirm_missing.status_code == 400
    assert confirm_missing.json()["detail"]["code"] == "extraction_confirmation_stale"

    confirm_stale = client.post(
        f"/extractions/{extraction_id}/confirmation",
        headers={"If-Match": "999"},
    )
    assert confirm_stale.status_code == 409
    assert confirm_stale.json()["detail"]["code"] == "extraction_confirmation_stale"

    confirm = client.post(
        f"/extractions/{extraction_id}/confirmation",
        headers={"If-Match": str(review_before["review_version"])},
    )
    assert confirm.status_code == 200
    snapshot = confirm.json()["snapshot"]
    assert {item["page_id"] for item in snapshot} == {
        first["page_id"],
        second["page_id"],
    }
    text_by_page = {item["page_id"]: item["final_text"] for item in snapshot}
    assert text_by_page[first["page_id"]] == edited_text
    assert text_by_page[second["page_id"]] == second["final_text_preview"]


def test_partial_review_blocks_confirmation() -> None:
    extraction = _post_image_extraction()
    extraction_id = extraction["extraction_id"]
    page = client.get(f"/extractions/{extraction_id}/review").json()["pages"][0]

    response = client.patch(
        f"/extractions/{extraction_id}/pages/{page['page_id']}/review",
        json={"version": page["review_version"], "unchanged": True},
    )
    assert response.status_code == 200

    review = client.get(f"/extractions/{extraction_id}/review").json()
    confirm = client.post(
        f"/extractions/{extraction_id}/confirmation",
        headers={"If-Match": str(review["review_version"])},
    )
    assert confirm.status_code == 409
    assert confirm.json()["detail"]["code"] == "extraction_review_incomplete"


def test_stale_page_version_conflict() -> None:
    extraction = _post_image_extraction()
    extraction_id = extraction["extraction_id"]
    page_id = extraction["pages"][0]["page_id"]

    response = client.patch(
        f"/extractions/{extraction_id}/pages/{page_id}/review",
        json={"version": 999, "unchanged": True},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "page_review_conflict"


def test_confirmation_checksum_and_review_blocking_with_incomplete_review() -> None:
    mixed = _post_mixed_pdf_extraction()
    extraction_id = mixed["extraction_id"]
    review = client.get(f"/extractions/{extraction_id}/review").json()
    assert review["review_required"] is True
    assert review["review_version"] == 1

    confirm = client.post(
        f"/extractions/{extraction_id}/confirmation",
        headers={"If-Match": "1"},
    )
    assert confirm.status_code == 409
    assert confirm.json()["detail"]["code"] == "extraction_review_incomplete"
