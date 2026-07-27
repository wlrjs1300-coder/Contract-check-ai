from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.models import AnalysisJob, AnalysisResultItem
from backend.app.main import app
from backend.app.services.analysis_evidence_encryption import (
    decrypt_analysis_evidence_list,
)
from backend.tests.support import TEST_USER_ID


client = TestClient(app)


def _create_result_item(
    db: Session,
) -> tuple[str, AnalysisResultItem]:
    upload = client.post(
        "/documents/upload",
        files={
            "file": (
                "canonical-storage.sample.txt",
                "1. Payment must be made within thirty days.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]
    created = client.post(f"/documents/{document_id}/analysis-jobs")
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    db.expire_all()
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id))
    assert job is not None
    assert len(job.result_items) == 1
    return document_id, job.result_items[0]


def _replace_extra_data(
    db: Session,
    item: AnalysisResultItem,
    value: dict[str, object],
) -> None:
    item.extra_data = value
    db.add(item)
    db.commit()


def _results(document_id: str):
    return client.get(f"/documents/{document_id}/analysis-results")


def test_new_row_has_only_nested_canonical_evidence(db_session: Session) -> None:
    document_id, item = _create_result_item(db_session)
    extra = item.extra_data
    assert "evidence" not in extra
    nested = extra["analysis_value"]["evidence"]
    assert nested
    assert "source_text" not in nested[0]
    assert "source_text_encrypted" in nested[0]
    assert "evidence_snapshot_hash" in extra
    assert "snapshot_version" in extra

    response = _results(document_id)
    assert response.status_code == 200
    evidence = response.json()["items"][0]["evidence"]
    assert evidence
    assert evidence[0]["source_text"]
    assert "source_text_encrypted" not in evidence[0]


def test_nested_only_and_empty_nested_evidence_are_allowed(
    db_session: Session,
) -> None:
    document_id, item = _create_result_item(db_session)
    assert _results(document_id).status_code == 200

    extra = deepcopy(item.extra_data)
    extra["analysis_value"]["evidence"] = []
    _replace_extra_data(db_session, item, extra)
    response = _results(document_id)
    assert response.status_code == 200
    assert response.json()["items"][0]["evidence"] == []


def test_identical_pr5_duplicate_is_allowed_but_nested_is_canonical(
    db_session: Session,
) -> None:
    document_id, item = _create_result_item(db_session)
    extra = deepcopy(item.extra_data)
    nested = extra["analysis_value"]["evidence"]
    extra["evidence"] = deepcopy(nested)
    _replace_extra_data(db_session, item, extra)

    response = _results(document_id)
    assert response.status_code == 200
    assert response.json()["items"][0]["evidence"][0]["source_text"]


@pytest.mark.parametrize(
    "top_level",
    [
        [],
        "malformed",
        [{"source_text": "legacy plaintext"}],
    ],
)
def test_mismatched_or_malformed_top_level_evidence_fails_closed(
    db_session: Session,
    top_level: object,
) -> None:
    document_id, item = _create_result_item(db_session)
    extra = deepcopy(item.extra_data)
    extra["evidence"] = top_level
    _replace_extra_data(db_session, item, extra)
    response = _results(document_id)
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Stored encrypted data is unavailable."
    }


@pytest.mark.parametrize(
    "top_level_factory",
    [
        lambda nested: deepcopy(nested),
        lambda nested: [{"source_text": "legacy plaintext"}],
        lambda nested: [],
    ],
)
def test_top_level_only_evidence_fails_closed(
    db_session: Session,
    top_level_factory,
) -> None:
    document_id, item = _create_result_item(db_session)
    extra = deepcopy(item.extra_data)
    nested = extra["analysis_value"]["evidence"]
    extra.pop("analysis_value")
    extra["evidence"] = top_level_factory(nested)
    _replace_extra_data(db_session, item, extra)
    assert _results(document_id).status_code == 500


def test_auxiliary_row_without_analysis_value_or_evidence_is_allowed(
    db_session: Session,
) -> None:
    document_id, item = _create_result_item(db_session)
    extra = deepcopy(item.extra_data)
    extra.pop("analysis_value")
    _replace_extra_data(db_session, item, extra)
    response = _results(document_id)
    assert response.status_code == 200
    assert response.json()["items"][0]["evidence"] == []


def test_nested_plaintext_evidence_fails_closed(db_session: Session) -> None:
    document_id, item = _create_result_item(db_session)
    extra = deepcopy(item.extra_data)
    nested = extra["analysis_value"]["evidence"]
    plaintext = decrypt_analysis_evidence_list(
        nested,
        analysis_job_id=item.analysis_job_id,
        clause_record_id=item.clause_record_id,
        owner_id=TEST_USER_ID,
        keyring=get_encryption_keyring(),
    )
    extra["analysis_value"]["evidence"] = plaintext
    _replace_extra_data(db_session, item, extra)
    assert _results(document_id).status_code == 500


def test_missing_nested_evidence_key_fails_closed(db_session: Session) -> None:
    document_id, item = _create_result_item(db_session)
    extra = deepcopy(item.extra_data)
    extra["analysis_value"].pop("evidence")
    _replace_extra_data(db_session, item, extra)
    assert _results(document_id).status_code == 500
