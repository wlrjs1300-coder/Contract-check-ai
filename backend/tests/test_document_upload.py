from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


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

    assert response.status_code == 415
    assert response.json() == {
        "detail": {
            "code": "UNSUPPORTED_FILE_TYPE",
            "message": "Only UTF-8 text files are supported.",
        }
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
        "detail": {
            "code": "EMPTY_FILE",
            "message": "The uploaded file is empty.",
        }
    }


def test_reject_mime_mismatch_and_double_extension() -> None:
    mime_response = client.post(
        "/documents/upload",
        files={"file": ("contract.txt", b"safe text", "application/pdf")},
    )
    double_response = client.post(
        "/documents/upload",
        files={"file": ("contract.exe.txt", b"safe text", "text/plain")},
    )
    assert mime_response.status_code == 415
    assert double_response.status_code == 415


def test_reject_zero_byte_nul_and_unsafe_filenames() -> None:
    nul_response = client.post(
        "/documents/upload",
        files={"file": ("contract.txt", b"safe\x00text", "text/plain")},
    )
    assert nul_response.status_code == 400
    for filename in ("../contract.txt", "..\\contract.txt", "bad\nname.txt"):
        response = client.post(
            "/documents/upload",
            files={"file": (filename, b"safe text", "text/plain")},
        )
        assert response.status_code == 400
        assert filename not in response.text


def test_upload_limit_is_enforced_during_chunk_read(monkeypatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "8")
    response = client.post(
        "/documents/upload",
        files={"file": ("contract.txt", b"123456789", "text/plain")},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "UPLOAD_TOO_LARGE"
    assert "contract.txt" not in response.text
