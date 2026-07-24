import pytest
from fastapi.testclient import TestClient
from PIL import Image
from io import BytesIO

from backend.app.api import analysis_jobs as analysis_jobs_api
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.services import analysis_pipeline
from backend.app.services.scalar_encryption import decrypt_clause_body
from backend.tests.support import TEST_USER_ID

from backend.app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def force_test_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")


def _png_bytes() -> bytes:
    image = Image.new("RGB", (1200, 1200), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _post_image_extraction() -> dict[str, object]:
    response = client.post(
        "/extractions/images",
        files=[
            ("files", ("page1.png", _png_bytes(), "image/png")),
            ("files", ("page2.png", _png_bytes(), "image/png")),
        ],
    )
    assert response.status_code == 201
    return response.json()


def _confirm_image_extraction_with_edit() -> tuple[str, int, str]:
    body = _post_image_extraction()
    extraction_id = body["extraction_id"]

    first_review = client.get(f"/extractions/{extraction_id}/review").json()
    first_page_id = first_review["pages"][0]["page_id"]
    first_version = first_review["pages"][0]["review_version"]
    edited_text = "수정된 OCR 페이지 본문"
    patch1 = client.patch(
        f"/extractions/{extraction_id}/pages/{first_page_id}/review",
        json={"reviewed_text": edited_text, "version": first_version},
    )
    assert patch1.status_code == 200

    second_review = client.get(f"/extractions/{extraction_id}/review").json()
    second_page_id = second_review["pages"][1]["page_id"]
    second_version = second_review["pages"][1]["review_version"]
    patch2 = client.patch(
        f"/extractions/{extraction_id}/pages/{second_page_id}/review",
        json={"unchanged": True, "version": second_version},
    )
    assert patch2.status_code == 200
    latest_review = client.get(f"/extractions/{extraction_id}/review").json()

    confirmation_response = client.post(
        f"/extractions/{extraction_id}/confirmation",
        headers={"If-Match": str(latest_review["review_version"])},
    )
    assert confirmation_response.status_code == 200
    confirmation = confirmation_response.json()
    return (
        extraction_id,
        confirmation["snapshot_version"],
        edited_text,
    )


def test_create_analysis_job_and_get_results() -> None:
    upload_response = client.post(
        "/documents/upload",
        files={
            "file": (
                "employment-contract.sample.txt",
                "제1조 근로조건",
                "text/plain",
            )
        },
    )

    assert upload_response.status_code == 200

    document = upload_response.json()
    document_id = document["document_id"]

    create_response = client.post(
        f"/documents/{document_id}/analysis-jobs"
    )

    assert create_response.status_code == 200

    job = create_response.json()
    assert job["job_id"]
    assert job["document_id"] == document_id
    assert job["status"] == "completed"

    get_response = client.get(
        f"/analysis-jobs/{job['job_id']}"
    )

    assert get_response.status_code == 200
    assert get_response.json() == job

    result_response = client.get(
        f"/documents/{document_id}/analysis-results"
    )

    assert result_response.status_code == 200

    result = result_response.json()
    assert result["document_id"] == document_id
    assert result["job_id"] == job["job_id"]
    assert result["status"] == "completed"
    assert len(result["items"]) == 1
    assert result["items"][0]["clause_id"] == "clause-001"
    assert result["items"][0]["display_label"] == "추가 확인"
    assert result["items"][0]["summary"] == "합성 분석 결과입니다."
    assert result["items"][0]["expert_review_recommended"] is False
    assert result["snapshot_stale"] is False
    assert result["items"][0]["is_stale"] is False
    assert result["items"][0]["evidence"]
    assert result["items"][0]["evidence"][0]["document_id"] == document_id


def test_reject_analysis_job_for_missing_document() -> None:
    response = client.post(
        "/documents/missing-document/analysis-jobs"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }


def test_get_missing_analysis_job() -> None:
    response = client.get("/analysis-jobs/missing-job")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Analysis job not found."
    }


def test_get_results_before_analysis() -> None:
    upload_response = client.post(
        "/documents/upload",
        files={
            "file": (
                "employment-contract.sample.txt",
                "제1조 근로조건",
                "text/plain",
            )
        },
    )

    assert upload_response.status_code == 200

    document_id = upload_response.json()["document_id"]

    response = client.get(
        f"/documents/{document_id}/analysis-results"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Analysis result not found."
    }



def test_failed_analysis_job_is_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_response = client.post(
        "/documents/upload",
        files={
            "file": (
                "failed-analysis.sample.txt",
                "1. Synthetic contract clause.",
                "text/plain",
            )
        },
    )

    assert upload_response.status_code == 200

    document_id = upload_response.json()["document_id"]
    job_id = "failed-analysis-job"

    monkeypatch.setattr(
        analysis_jobs_api,
        "uuid4",
        lambda: job_id,
    )

    def reject_reference_id(*args, **kwargs) -> None:
        raise ValueError("Forced analysis failure.")

    monkeypatch.setattr(
        analysis_pipeline,
        "validate_reference_id",
        reject_reference_id,
    )

    with pytest.raises(
        ValueError,
        match="Forced analysis failure",
    ):
        client.post(
            f"/documents/{document_id}/analysis-jobs"
        )

    response = client.get(f"/analysis-jobs/{job_id}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job_id,
        "document_id": document_id,
        "status": "failed",
    }


def test_extraction_analysis_job_requires_confirmation(
) -> None:
    body = _post_image_extraction()
    extraction_id = body["extraction_id"]

    response = client.post(
        f"/extractions/{extraction_id}/analysis-jobs",
        headers={"If-Match": "1"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "confirmation_required"


def test_extraction_analysis_job_rejects_stale_or_missing_if_match() -> None:
    extraction_id, _, _ = _confirm_image_extraction_with_edit()

    missing_if_match = client.post(f"/extractions/{extraction_id}/analysis-jobs")
    assert missing_if_match.status_code == 400
    assert missing_if_match.json()["detail"] == "If-Match header is required."

    stale_response = client.post(
        f"/extractions/{extraction_id}/analysis-jobs",
        headers={"If-Match": "999"},
    )
    assert stale_response.status_code == 409
    assert stale_response.json()["detail"] == "extraction revision mismatch"


def test_extraction_analysis_job_uses_confirmed_snapshot_as_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction_id, review_version, edited_text = (
        _confirm_image_extraction_with_edit()
    )
    captured_clauses: list[str] = []

    def _fake_run_analysis_pipeline(*args, **kwargs) -> None:
        clauses = kwargs.get("clauses") if "clauses" in kwargs else args[2]
        keyring = get_encryption_keyring()
        captured_clauses.extend(
            [
                decrypt_clause_body(
                    clause.body_encrypted,
                    clause_id=clause.id,
                    owner_id=TEST_USER_ID,
                    keyring=keyring,
                )
                for clause in clauses
            ]
        )

        job = kwargs["job"]
        db = kwargs["db"]
        job.status = "completed"
        db.add(job)
        db.commit()
        db.refresh(job)

    monkeypatch.setattr(
        analysis_jobs_api,
        "run_analysis_pipeline",
        _fake_run_analysis_pipeline,
    )

    response = client.post(
        f"/extractions/{extraction_id}/analysis-jobs",
        headers={"If-Match": str(review_version)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert edited_text in captured_clauses
