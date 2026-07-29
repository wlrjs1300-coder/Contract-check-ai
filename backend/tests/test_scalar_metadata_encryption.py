from __future__ import annotations

import base64
import hashlib
import re

import pytest

from backend.app.core.crypto import EncryptionEnvelope
from backend.app.core.email_lookup import (
    EmailLookupConfigurationError,
    build_email_lookup_hash,
    compare_email_lookup_hash,
    get_email_lookup_key,
)
from backend.app.core.encryption_config import (
    EncryptionKey,
    EncryptionKeyring,
    get_encryption_keyring,
)
from backend.app.services.scalar_encryption import (
    ScalarDecryptionError,
    encrypt_clause_body,
)
from backend.app.services.scalar_metadata_encryption import (
    decrypt_clause_title,
    decrypt_document_filename,
    decrypt_extraction_filename_display,
    decrypt_user_email,
    encrypt_clause_title,
    encrypt_document_filename,
    encrypt_extraction_filename_display,
    encrypt_user_email,
)


def _keyring() -> EncryptionKeyring:
    return get_encryption_keyring()


def test_user_email_scalar_metadata_round_trip() -> None:
    encrypted = encrypt_user_email(
        "user@example.invalid", user_id="user-1", keyring=_keyring()
    )
    assert decrypt_user_email(
        encrypted, user_id="user-1", keyring=_keyring()
    ) == "user@example.invalid"


def test_user_email_ciphertext_rejects_cross_user_swap() -> None:
    encrypted = encrypt_user_email(
        "user@example.invalid", user_id="user-1", keyring=_keyring()
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_user_email(encrypted, user_id="user-2", keyring=_keyring())


def test_document_filename_round_trip() -> None:
    encrypted = encrypt_document_filename(
        "contract.txt",
        record_id="document-1",
        owner_id="owner-1",
        keyring=_keyring(),
    )
    assert decrypt_document_filename(
        encrypted,
        record_id="document-1",
        owner_id="owner-1",
        keyring=_keyring(),
    ) == "contract.txt"


def test_document_filename_rejects_cross_document_swap() -> None:
    encrypted = encrypt_document_filename(
        "contract.txt",
        record_id="document-1",
        owner_id="owner-1",
        keyring=_keyring(),
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_document_filename(
            encrypted,
            record_id="document-2",
            owner_id="owner-1",
            keyring=_keyring(),
        )


def test_extraction_filename_display_round_trip() -> None:
    encrypted = encrypt_extraction_filename_display(
        "contract.pdf",
        record_id="extraction-1",
        owner_id="owner-1",
        keyring=_keyring(),
    )
    assert decrypt_extraction_filename_display(
        encrypted,
        record_id="extraction-1",
        owner_id="owner-1",
        keyring=_keyring(),
    ) == "contract.pdf"


def test_extraction_filename_rejects_cross_extraction_swap() -> None:
    encrypted = encrypt_extraction_filename_display(
        "contract.pdf",
        record_id="extraction-1",
        owner_id="owner-1",
        keyring=_keyring(),
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_extraction_filename_display(
            encrypted,
            record_id="extraction-2",
            owner_id="owner-1",
            keyring=_keyring(),
        )


def test_clause_title_round_trip() -> None:
    encrypted = encrypt_clause_title(
        "계약 목적",
        clause_id="clause-1",
        owner_id="owner-1",
        keyring=_keyring(),
    )
    assert decrypt_clause_title(
        encrypted,
        clause_id="clause-1",
        owner_id="owner-1",
        keyring=_keyring(),
    ) == "계약 목적"


def test_clause_title_null_is_preserved() -> None:
    assert encrypt_clause_title(
        None,
        clause_id="clause-1",
        owner_id="owner-1",
        keyring=_keyring(),
    ) is None
    assert decrypt_clause_title(
        None,
        clause_id="clause-1",
        owner_id="owner-1",
        keyring=_keyring(),
    ) is None


def test_clause_title_rejects_cross_clause_swap() -> None:
    encrypted = encrypt_clause_title(
        "title",
        clause_id="clause-1",
        owner_id="owner-1",
        keyring=_keyring(),
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_title(
            encrypted,
            clause_id="clause-2",
            owner_id="owner-1",
            keyring=_keyring(),
        )


def test_clause_title_rejects_clause_body_ciphertext() -> None:
    encrypted_body = encrypt_clause_body(
        "body",
        clause_id="clause-1",
        owner_id="owner-1",
        keyring=_keyring(),
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_clause_title(
            encrypted_body,
            clause_id="clause-1",
            owner_id="owner-1",
            keyring=_keyring(),
        )


def test_scalar_metadata_unknown_key_fails_closed() -> None:
    encrypted = encrypt_user_email(
        "user@example.invalid", user_id="user-1", keyring=_keyring()
    )
    unknown_keyring = EncryptionKeyring(
        _keys=(EncryptionKey("other-key", b"x" * 32, "active"),),
        _active_key_id="other-key",
    )
    with pytest.raises(ScalarDecryptionError):
        decrypt_user_email(
            encrypted, user_id="user-1", keyring=unknown_keyring
        )


def test_scalar_metadata_tampered_ciphertext_fails_closed() -> None:
    encrypted = encrypt_user_email(
        "user@example.invalid", user_id="user-1", keyring=_keyring()
    )
    envelope = EncryptionEnvelope.from_json(encrypted).to_mapping()
    ciphertext = str(envelope["ciphertext"])
    envelope["ciphertext"] = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
    tampered = EncryptionEnvelope.from_mapping(envelope).to_json()
    with pytest.raises(ScalarDecryptionError):
        decrypt_user_email(tampered, user_id="user-1", keyring=_keyring())


def test_email_lookup_hmac_is_stable_for_same_normalized_email() -> None:
    assert build_email_lookup_hash(" User@Example.invalid ") == (
        build_email_lookup_hash("user@example.invalid")
    )


def test_email_lookup_hmac_changes_for_different_email() -> None:
    assert build_email_lookup_hash("one@example.invalid") != (
        build_email_lookup_hash("two@example.invalid")
    )


def test_email_lookup_hmac_differs_from_plain_sha256() -> None:
    email = "user@example.invalid"
    assert build_email_lookup_hash(email) != hashlib.sha256(email.encode()).hexdigest()


def test_email_lookup_hmac_returns_lowercase_hex_64() -> None:
    value = build_email_lookup_hash("user@example.invalid")
    assert re.fullmatch(r"[0-9a-f]{64}", value)


@pytest.mark.parametrize("value", [None, "", " "])
def test_email_lookup_hmac_rejects_missing_key(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("EMAIL_LOOKUP_HMAC_KEY", raising=False)
    else:
        monkeypatch.setenv("EMAIL_LOOKUP_HMAC_KEY", value)
    with pytest.raises(EmailLookupConfigurationError):
        get_email_lookup_key()


def test_email_lookup_hmac_rejects_malformed_base64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMAIL_LOOKUP_HMAC_KEY", "not-base64!")
    with pytest.raises(EmailLookupConfigurationError):
        get_email_lookup_key()


def test_email_lookup_hmac_rejects_short_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "EMAIL_LOOKUP_HMAC_KEY",
        base64.b64encode(b"short").decode(),
    )
    with pytest.raises(EmailLookupConfigurationError):
        get_email_lookup_key()


def test_email_lookup_compare_uses_constant_time_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def _compare(first: str, second: str) -> bool:
        calls.append((first, second))
        return True

    monkeypatch.setattr("hmac.compare_digest", _compare)
    assert compare_email_lookup_hash("a", "b") is True
    assert calls == [("a", "b")]
