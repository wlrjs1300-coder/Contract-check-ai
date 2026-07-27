from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.commands.scalar_metadata_backfill import backfill, inventory
from backend.app.core.email_lookup import build_email_lookup_hash
from backend.app.db.models import Document, User
from backend.app.main import app
from backend.app.services.scalar_encryption import ScalarDecryptionError
from backend.app.services.scalar_metadata_transition import (
    resolve_transition_scalar,
)


client = TestClient(app)


def test_transition_scalar_states_and_mismatch() -> None:
    assert resolve_transition_scalar(
        "value", None, encrypted_present=False, allow_missing=False
    ).state == "legacy_plaintext"
    assert resolve_transition_scalar(
        "value", "value", encrypted_present=True, allow_missing=False
    ).state == "matching_dual"
    assert resolve_transition_scalar(
        None, "value", encrypted_present=True, allow_missing=False
    ).state == "encrypted_only"
    assert resolve_transition_scalar(
        None, None, encrypted_present=False, allow_missing=True
    ).state == "missing"
    with pytest.raises(ScalarDecryptionError):
        resolve_transition_scalar(
            "plaintext",
            "different",
            encrypted_present=True,
            allow_missing=False,
        )


def test_register_writes_plaintext_encrypted_and_lookup_hash(
    db_session: Session,
) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": " Transition@Example.invalid ",
            "password": "Password12345!",
        },
    )
    assert response.status_code == 200
    assert response.json()["email"] == "transition@example.invalid"
    user = db_session.scalar(
        select(User).where(User.id == response.json()["user_id"])
    )
    assert user is not None
    assert user.email == "transition@example.invalid"
    assert user.email_encrypted is not None
    assert "transition@example.invalid" not in user.email_encrypted
    assert user.email_lookup_hash == build_email_lookup_hash(user.email)


def test_login_prefers_email_lookup_hash(db_session: Session) -> None:
    registered = client.post(
        "/auth/register",
        json={
            "email": "lookup@example.invalid",
            "password": "Password12345!",
        },
    )
    user = db_session.scalar(
        select(User).where(User.id == registered.json()["user_id"])
    )
    assert user is not None
    user.email = "different-legacy@example.invalid"
    db_session.commit()
    response = client.post(
        "/auth/login",
        json={
            "email": "lookup@example.invalid",
            "password": "Password12345!",
        },
    )
    assert response.status_code == 500


def test_document_upload_dual_writes_filename(db_session: Session) -> None:
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "transition-contract.txt",
                "제1조 계약 목적",
                "text/plain",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "transition-contract.txt"
    document = db_session.scalar(
        select(Document).where(Document.id == response.json()["document_id"])
    )
    assert document is not None
    assert document.filename == "transition-contract.txt"
    assert document.filename_encrypted is not None
    assert "transition-contract.txt" not in document.filename_encrypted
    assert document.clauses[0].title_encrypted is not None


def test_document_filename_mismatch_fails_closed(db_session: Session) -> None:
    response = client.post(
        "/documents/upload",
        files={"file": ("original.txt", "제1조 목적", "text/plain")},
    )
    document = db_session.scalar(
        select(Document).where(Document.id == response.json()["document_id"])
    )
    assert document is not None
    document.filename = "mismatch.txt"
    db_session.commit()
    result = client.get(f"/documents/{document.id}")
    assert result.status_code == 500
    assert "original.txt" not in result.text
    assert "mismatch.txt" not in result.text


def test_backfill_plaintext_only_rows_is_idempotent(
    db_session: Session,
) -> None:
    before = inventory(db_session)
    assert before["users"].plaintext_only >= 1
    first = backfill(db_session, batch_size=1)
    assert first["users"].updated >= 1
    second = backfill(db_session, batch_size=1)
    assert second["users"].updated == 0
    users = db_session.scalars(select(User)).all()
    assert all(user.email_encrypted for user in users)
    assert all(user.email_lookup_hash for user in users)


def test_inventory_output_contains_counts_not_plaintext(
    db_session: Session,
) -> None:
    secret = "inventory-secret@example.invalid"
    user = User(
        id="00000000-0000-4000-8000-000000000123",
        email=secret,
        password_hash="synthetic",
        is_active=True,
        auth_version=1,
    )
    db_session.add(user)
    db_session.commit()
    report = inventory(db_session)
    rendered = json.dumps(
        {
            name: values.__dict__
            for name, values in report.items()
        }
    )
    assert secret not in rendered
