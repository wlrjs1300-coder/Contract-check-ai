from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.models import Document
from backend.app.main import app
from backend.app.services.document_metadata_encryption import (
    decrypt_unclassified_sections,
    encrypt_unclassified_sections,
)
from backend.app.services.scalar_encryption import ScalarDecryptionError


client = TestClient(app)


def _encrypted(sections: list[str]) -> list[dict[str, object]]:
    return encrypt_unclassified_sections(
        sections,
        document_id="document-1",
        owner_id="owner-1",
        keyring=get_encryption_keyring(),
    )


def _decrypt(sections: list[dict[str, object]]) -> list[str]:
    return decrypt_unclassified_sections(
        sections,
        document_id="document-1",
        owner_id="owner-1",
        keyring=get_encryption_keyring(),
    )


def test_unclassified_sections_round_trip() -> None:
    plaintext = ["계약 당사자의 비공개 조건", ""]
    assert _decrypt(_encrypted(plaintext)) == plaintext


def test_unclassified_sections_empty_list_is_allowed() -> None:
    assert _encrypted([]) == []
    assert _decrypt([]) == []


def test_unclassified_sections_legacy_plaintext_fails_closed() -> None:
    with pytest.raises(ScalarDecryptionError):
        _decrypt(["legacy plaintext"])  # type: ignore[list-item]


def test_unclassified_sections_dual_write_fails_closed() -> None:
    encrypted = _encrypted(["secret"])
    encrypted[0]["text"] = "secret"
    with pytest.raises(ScalarDecryptionError):
        _decrypt(encrypted)


def test_unclassified_sections_ciphertext_rejects_cross_item_swap() -> None:
    encrypted = _encrypted(["first secret", "second secret"])
    swapped = deepcopy(encrypted)
    swapped[0]["text_encrypted"] = encrypted[1]["text_encrypted"]
    with pytest.raises(ScalarDecryptionError):
        _decrypt(swapped)


def test_unclassified_sections_wrong_owner_fails_closed() -> None:
    encrypted = _encrypted(["secret"])
    with pytest.raises(ScalarDecryptionError):
        decrypt_unclassified_sections(
            encrypted,
            document_id="document-1",
            owner_id="owner-2",
            keyring=get_encryption_keyring(),
        )


def test_raw_database_never_stores_unclassified_contract_sections(
    db_session: Session,
) -> None:
    secret = "미분류된 민감 계약 조건"
    response = client.post(
        "/documents/upload",
        files={"file": ("contract.txt", secret, "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["unclassified_sections"] == [secret]

    document = db_session.scalar(
        select(Document).where(Document.id == response.json()["document_id"])
    )
    assert document is not None
    assert secret not in str(document.unclassified_sections)
    assert document.unclassified_sections[0]["text_encrypted"]["ciphertext"]


def test_document_unclassified_sections_round_trip_after_owner_check() -> None:
    secret = "소유자에게만 반환할 미분류 계약 조건"
    uploaded = client.post(
        "/documents/upload",
        files={"file": ("contract.txt", secret, "text/plain")},
    )
    response = client.get(f"/documents/{uploaded.json()['document_id']}")
    assert response.status_code == 200
    assert response.json()["unclassified_sections"] == [secret]
