import pytest
from fastapi.testclient import TestClient

from backend.app.api import analysis_jobs as analysis_jobs_api
from backend.app.services import analysis_pipeline

from backend.app.main import app


client = TestClient(app)


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
