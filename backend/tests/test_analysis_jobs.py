from fastapi.testclient import TestClient

from backend.app.api.analysis_jobs import analysis_jobs
from backend.app.main import app


client = TestClient(app)


def setup_function() -> None:
    analysis_jobs.clear()


def test_create_and_get_analysis_job() -> None:
    create_response = client.post(
        "/documents/doc-test/analysis-jobs"
    )

    assert create_response.status_code == 200

    created_job = create_response.json()
    assert created_job["job_id"]
    assert created_job["document_id"] == "doc-test"
    assert created_job["status"] == "queued"

    get_response = client.get(
        f"/analysis-jobs/{created_job['job_id']}"
    )

    assert get_response.status_code == 200
    assert get_response.json() == created_job


def test_get_missing_analysis_job() -> None:
    response = client.get("/analysis-jobs/missing-job")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Analysis job not found."
    }
