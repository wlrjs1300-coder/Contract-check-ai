from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.auth import get_current_user
from backend.app.db.models import AnalysisJob, Clause, Document, Extraction, ExtractionPage
from backend.app.main import app

client = TestClient(app)


@contextmanager
def _use_real_auth():
    removed = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield
    finally:
        if removed is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = removed


def _register_and_login(email: str) -> tuple[str, str]:
    password = "SecurePassword123"
    register_response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 200
    register_body = register_response.json()

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    login_body = login_response.json()

    return register_body["user_id"], login_body["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_document_for_user(token: str, filename: str = "sample.txt") -> str:
    headers = _auth_headers(token)
    response = client.post(
        "/documents/upload",
        files={"file": (filename, b"Clause\n\nSection 1\n", "text/plain")},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["document_id"]


def _create_extraction_for_user(
    db_session: Session,
    user_id: str,
    *,
    extraction_id: str,
) -> str:
    extraction = Extraction(
        id=extraction_id,
        filename_display="sample.pdf",
        source_type="pdf",
        size_bytes=12,
        page_count=1,
        status="confirmed",
        method="pdf",
        warnings=[],
        requires_user_review=False,
        owner_id=user_id,
        extra_data={
            "review_status": "confirmed",
            "review_version": 1,
            "snapshot_version": 1,
            "confirmation_snapshot": [
                {
                    "page_id": "1",
                    "page_number": 1,
                    "final_text": "Synthetic extracted text.",
                    "text_source": "original",
                    "text_changed": False,
                    "method": "direct",
                    "warnings": [],
                }
            ],
            "final_total_text_length": 24,
            "confirmation_checksum": "deadbeef",
        },
    )
    db_session.add(extraction)
    db_session.flush()

    page = ExtractionPage(
        extraction_id=extraction_id,
        page_number=1,
        method="direct",
        text="Synthetic extracted text.",
        warnings=[],
        requires_user_review=False,
        extra_data={
            "page_id": "1",
            "review_status": "confirmed",
            "review_version": 1,
            "reviewed_text": "Synthetic extracted text.",
            "text_changed": False,
            "text_source": "original",
            "final_text": "Synthetic extracted text.",
            "analysis_blocked": False,
        },
    )
    db_session.add(page)
    db_session.commit()
    return extraction_id


def test_document_isolation_between_users(
    db_session: Session,
) -> None:
    with _use_real_auth():
        user_a_id, token_a = _register_and_login("owner-a@example.invalid")
        user_b_id, token_b = _register_and_login("owner-b@example.invalid")

        document_id = _create_document_for_user(token_a)

        response = client.get(
            f"/documents/{document_id}",
            headers=_auth_headers(token_b),
        )
        assert response.status_code == 404

        analysis_job_response = client.post(
            f"/documents/{document_id}/analysis-jobs",
            headers=_auth_headers(token_b),
        )
        assert analysis_job_response.status_code == 404

        result_response = client.get(
            f"/documents/{document_id}/analysis-results",
            headers=_auth_headers(token_b),
        )
        assert result_response.status_code == 404

        my_job = client.post(
            f"/documents/{document_id}/analysis-jobs",
            headers=_auth_headers(token_a),
        )
        assert my_job.status_code == 200
        job_id = my_job.json()["job_id"]

        other_job = client.get(
            f"/analysis-jobs/{job_id}",
            headers=_auth_headers(token_b),
        )
        assert other_job.status_code == 404

        assert user_a_id and user_b_id
        assert user_a_id != user_b_id


def test_extraction_isolation_between_users(
    db_session: Session,
) -> None:
    user_a_id, token_a = _register_and_login("owner-a-extraction@example.invalid")
    _, token_b = _register_and_login("owner-b-extraction@example.invalid")

    extraction_id = str(uuid4())
    with _use_real_auth():
        _create_extraction_for_user(
            db_session,
            user_a_id,
            extraction_id=extraction_id,
        )

        response = client.get(
            f"/extractions/{extraction_id}",
            headers=_auth_headers(token_b),
        )
        assert response.status_code == 404

        review_response = client.get(
            f"/extractions/{extraction_id}/review",
            headers=_auth_headers(token_b),
        )
        assert review_response.status_code == 404

        patch_response = client.patch(
            f"/extractions/{extraction_id}/pages/1/review",
            json={"reviewed_text": "override text", "version": 1},
            headers=_auth_headers(token_b),
        )
        assert patch_response.status_code == 404

        confirm_response = client.post(
            f"/extractions/{extraction_id}/confirmation",
            headers={**_auth_headers(token_b), "If-Match": '"1"'},
        )
        assert confirm_response.status_code == 404

        job_response = client.post(
            f"/extractions/{extraction_id}/analysis-jobs",
            headers={**_auth_headers(token_b), "If-Match": '"1"'},
        )
        assert job_response.status_code == 404


def _snapshot_checksum(snapshot: list[dict[str, object]]) -> str:
    from hashlib import sha256

    hasher = sha256()
    for item in snapshot:
        hasher.update(str(item["final_text"]).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def test_extraction_cross_user_document_id_collision_isolation(db_session: Session) -> None:
    user_a_id, token_a = _register_and_login("collision-a@example.invalid")
    user_b_id, _ = _register_and_login("collision-b@example.invalid")

    extraction_id = str(uuid4())
    with _use_real_auth():
        _create_extraction_for_user(
            db_session,
            user_a_id,
            extraction_id=extraction_id,
        )
        extraction = db_session.get(Extraction, extraction_id)
        assert extraction is not None
        expected_checksum = _snapshot_checksum(
            extraction.extra_data["confirmation_snapshot"],
        )
        extraction.extra_data = {
            **extraction.extra_data,
            "confirmation_checksum": expected_checksum,
        }
        db_session.add(extraction)
        db_session.commit()
        assert (
            extraction.extra_data["confirmation_checksum"] == expected_checksum
        )

        conflicting_document = Document(
            id=extraction_id,
            owner_id=user_b_id,
            filename="existing-b.txt",
            content_type="text/plain",
            size_bytes=12,
            character_count=24,
            status="processed",
            unclassified_sections=[],
            document_warnings=[],
        )
        conflicting_clause = Clause(
            id=str(uuid4()),
            clause_id="clause-b-001",
            reference_id="conflict:clause:1",
            source_hash="conflict-source-hash",
            ordinal=1,
            marker="1.",
            clause_type="normal",
            title="ConflictClause",
            body="Existing user B clause.",
            warnings=[],
        )
        conflicting_document.clauses.append(conflicting_clause)
        db_session.add(conflicting_document)
        db_session.commit()

        pre_jobs = (
            db_session.query(AnalysisJob)
            .filter(AnalysisJob.document_id == extraction_id)
            .all()
        )
        assert pre_jobs == []

        response = client.post(
            f"/extractions/{extraction_id}/analysis-jobs",
            headers={**_auth_headers(token_a), "If-Match": '"1"'},
        )
        assert response.status_code == 404
        body = response.json()
        assert body["detail"] == "Document not found."
        assert "owner_id" not in body
        assert "filename" not in body
        assert "clauses" not in body
        assert user_b_id not in str(body)

        documents = (
            db_session.query(Document)
            .filter(Document.id == extraction_id)
            .all()
        )
        assert len(documents) == 1
        assert documents[0].owner_id == user_b_id
        assert documents[0].filename == "existing-b.txt"
        assert documents[0].owner_id != user_a_id

        clauses = (
            db_session.query(Clause)
            .filter(Clause.document_id == extraction_id)
            .all()
        )
        assert len(clauses) == 1
        assert clauses[0].body == "Existing user B clause."
        assert clauses[0].reference_id == "conflict:clause:1"

        post_jobs = (
            db_session.query(AnalysisJob)
            .filter(AnalysisJob.document_id == extraction_id)
            .all()
        )
        assert post_jobs == pre_jobs

        assert body["detail"] == "Document not found."
