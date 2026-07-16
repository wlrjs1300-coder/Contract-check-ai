from fastapi.testclient import TestClient

from backend.app.db.database import Base, engine
from backend.app.main import app


client = TestClient(app)


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_upload_txt_document() -> None:
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "employment-contract.sample.txt",
                "제1조 근로조건",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["document_id"]
    assert body["filename"] == "employment-contract.sample.txt"
    assert body["content_type"] == "text/plain"
    assert body["size_bytes"] > 0
    assert body["character_count"] == len("제1조 근로조건")
    assert body["status"] == "processed"
    assert body["clause_count"] == 1
    assert len(body["clauses"]) == 1
    assert body["clauses"][0]["marker"] == "제1조"
    assert body["clauses"][0]["body"] == "근로조건"
    assert body["document_warnings"] == []


def test_upload_and_get_document() -> None:
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

    uploaded_document = upload_response.json()

    get_response = client.get(
        f"/documents/{uploaded_document['document_id']}"
    )

    assert get_response.status_code == 200
    assert get_response.json() == uploaded_document


def test_get_missing_document() -> None:
    response = client.get("/documents/missing-document")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found."
    }


def test_reject_non_txt_document() -> None:
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "contract.pdf",
                b"%PDF-test",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Only .txt files are allowed."
    }


def test_reject_empty_txt_document() -> None:
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "empty.sample.txt",
                b"",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "The uploaded file is empty."
    }
