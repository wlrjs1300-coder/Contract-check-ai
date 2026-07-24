from __future__ import annotations

import base64
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from backend.app.core.crypto import (
    AadValidationError,
    DecryptionFailedError,
    EncryptionEnvelope,
    EncryptionFailedError,
    EnvelopeValidationError,
    build_canonical_aad,
    decrypt,
    encrypt,
)
from backend.app.core.encryption_config import (
    EncryptionConfigurationError,
    KeyLookupError,
    get_encryption_keyring,
)
from backend.app.main import app


def _make_aad(**kwargs) -> bytes:
    return build_canonical_aad(
        resource_type=kwargs.get("resource_type", "document"),
        record_id=kwargs.get("record_id", "record-1"),
        field_name=kwargs.get("field_name", "clause"),
        owner_id=kwargs.get("owner_id", "owner-1"),
        schema_version=kwargs.get("schema_version", "v1"),
    )


def test_build_canonical_aad_rules_and_korean() -> None:
    first = _make_aad(
        owner_id="owner-1",
        resource_type="문서",
        record_id="문서-1",
        field_name="조항",
    )
    second = _make_aad(
        owner_id="owner-1",
        resource_type="문서",
        record_id="문서-1",
        field_name="조항",
    )
    assert first == second
    assert b'"owner_id":"owner-1"' in first
    assert '"resource_type":"문서"' in first.decode("utf-8")


@pytest.mark.parametrize(
    ("kwargs"),
    [
        {"record_id": ""},
        {"record_id": "  문서"},
        {"record_id": "문서  "},
        {"record_id": "문서\x00"},
        {"record_id": 1},  # type: ignore[arg-type]
        {"record_id": None},  # type: ignore[arg-type]
    ],
)
def test_build_canonical_aad_invalid(kwargs: dict) -> None:
    with pytest.raises(AadValidationError):
        _make_aad(**kwargs)


def test_aesgcm_roundtrip_text_variants() -> None:
    keyring = get_encryption_keyring()
    aad = _make_aad()
    for plaintext in [b"", b"\x00", b"\x00\x01", b"hello", "한글".encode("utf-8")]:
        env = encrypt(plaintext, aad=aad, keyring=keyring)
        assert env.enc_version == 1
        assert env.algorithm == "AES-256-GCM"
        assert env.key_id == "synthetic-key-v1"
        assert set(env.__dict__.keys()) == {"enc_version", "key_id", "algorithm", "nonce", "ciphertext"}
        restored = decrypt(env, aad=aad, keyring=keyring)
        assert restored == plaintext


def test_invalid_envelope_direct_construction() -> None:
    valid_nonce = base64.b64encode(b"\x00" * 12).decode("ascii")
    valid_ciphertext = base64.b64encode(b"\x00" * 16).decode("ascii")

    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope(
            enc_version=999,
            key_id="synthetic-key-v1",
            algorithm="AES-256-GCM",
            nonce=valid_nonce,
            ciphertext=valid_ciphertext,
        )

    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope(
            enc_version=1,
            key_id="INVALID KEY",
            algorithm="AES-256-GCM",
            nonce=valid_nonce,
            ciphertext=valid_ciphertext,
        )

    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope(
            enc_version=1,
            key_id="synthetic-key-v1",
            algorithm="AES-128-GCM",
            nonce=valid_nonce,
            ciphertext=valid_ciphertext,
        )

    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope(
            enc_version=1,
            key_id="synthetic-key-v1",
            algorithm="AES-256-GCM",
            nonce="not-base64",
            ciphertext=valid_ciphertext,
        )

    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope(
            enc_version=1,
            key_id="synthetic-key-v1",
            algorithm="AES-256-GCM",
            nonce=valid_nonce,
            ciphertext="not-base64",
        )


def test_aesgcm_nonce_and_ciphertext_randomized() -> None:
    keyring = get_encryption_keyring()
    aad = _make_aad()
    first = encrypt(b"same", aad=aad, keyring=keyring)
    second = encrypt(b"same", aad=aad, keyring=keyring)
    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext


def test_encrypt_rejects_non_bytes() -> None:
    keyring = get_encryption_keyring()
    aad = _make_aad()
    with pytest.raises(EncryptionFailedError):
        encrypt("text", aad=aad, keyring=keyring)  # type: ignore[arg-type]
    with pytest.raises(EncryptionFailedError):
        encrypt({"x": "y"}, aad=aad, keyring=keyring)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"enc_version": 2},
        {"algorithm": "AES-128-GCM"},
        {"key_id": 1},
        {"nonce": 1},
        {"ciphertext": 1},
        {"extra": "x"},
        {"ciphertext": "a"},
        {"nonce": "aGVsbG8"},
        {"enc_version": 1, "key_id": "synthetic-key-v1", "algorithm": "AES-256-GCM", "nonce": "aQ=="},
    ],
)
def test_envelope_validation_strict(changes: dict[str, object]) -> None:
    base = {
        "enc_version": 1,
        "key_id": "synthetic-key-v1",
        "algorithm": "AES-256-GCM",
        "nonce": base64.b64encode(b"\x00" * 12).decode("ascii"),
        "ciphertext": base64.b64encode(b"\x00" * 16).decode("ascii"),
    }
    base.update(changes)
    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope.from_mapping(base)


def test_decrypt_context_guard_and_tamper_failures() -> None:
    keyring = get_encryption_keyring()
    aad = _make_aad()
    env = encrypt(b"test", aad=aad, keyring=keyring)

    with pytest.raises(DecryptionFailedError):
        decrypt(env, aad=b"wrong", keyring=keyring)

    with pytest.raises(DecryptionFailedError):
        decrypt(env, aad=_make_aad(owner_id="owner-other"), keyring=keyring)

    tampered_nonce = EncryptionEnvelope(
        enc_version=env.enc_version,
        key_id=env.key_id,
        algorithm=env.algorithm,
        nonce=base64.b64encode(b"\x01" * 12).decode("ascii"),
        ciphertext=env.ciphertext,
    )
    with pytest.raises(DecryptionFailedError):
        decrypt(tampered_nonce, aad=aad, keyring=keyring)

    tampered_cipher_bytes = bytearray(base64.b64decode(env.ciphertext))
    tampered_cipher_bytes[0] ^= 0xFF
    tampered_cipher = EncryptionEnvelope(
        enc_version=env.enc_version,
        key_id=env.key_id,
        algorithm=env.algorithm,
        nonce=env.nonce,
        ciphertext=base64.b64encode(bytes(tampered_cipher_bytes)).decode("ascii"),
    )
    with pytest.raises(DecryptionFailedError):
        decrypt(tampered_cipher, aad=aad, keyring=keyring)


def test_unknown_key_id_and_unsupported_algorithm(monkeypatch: pytest.MonkeyPatch) -> None:
    keyring = get_encryption_keyring()
    with pytest.raises(DecryptionFailedError):
        decrypt(
            EncryptionEnvelope(
                enc_version=1,
                key_id="unknown",
                algorithm="AES-256-GCM",
                nonce=base64.b64encode(b"\x00" * 12).decode("ascii"),
                ciphertext=base64.b64encode(b"\x00" * 16).decode("ascii"),
            ),
            aad=_make_aad(),
            keyring=keyring,
        )

    sample_nonce = base64.b64encode(b"\x00" * 12).decode("ascii")
    sample_ciphertext = base64.b64encode(b"\x00" * 16).decode("ascii")
    unknown_env = EncryptionEnvelope(
        enc_version=1,
        key_id="synthetic-key-v1",
        algorithm="AES-256-GCM",
        nonce=sample_nonce,
        ciphertext=sample_ciphertext,
    )
    envelope_repr = repr(unknown_env)
    assert sample_nonce not in envelope_repr
    assert sample_ciphertext not in envelope_repr

    with pytest.raises(EnvelopeValidationError):
        EncryptionEnvelope.from_mapping(
            {
                "enc_version": 1,
                "key_id": "synthetic-key-v1",
                "algorithm": "AES-128-GCM",
                "nonce": base64.b64encode(b"\x00" * 12).decode("ascii"),
                "ciphertext": base64.b64encode(b"\x00" * 16).decode("ascii"),
            }
        )


def test_decrypt_only_key_is_accepted() -> None:
    aes_key = bytes(range(32, 64))
    keyring = get_encryption_keyring()
    aad = _make_aad()
    envelope_text = EncryptionEnvelope(
        enc_version=1,
        key_id="synthetic-key-v0",
        algorithm="AES-256-GCM",
        nonce=base64.b64encode(b"\x02" * 12).decode("ascii"),
        ciphertext=base64.b64encode(AESGCM(aes_key).encrypt(b"\x02" * 12, b"legacy", aad)).decode("ascii"),
    )

    # Keep existing default keyring: decrypt-only key can be used at decrypt time only.
    assert decrypt(envelope_text, aad=aad, keyring=keyring) == b"legacy"


def test_get_key_unknown_key_raises_key_lookup_error() -> None:
    keyring = get_encryption_keyring()
    with pytest.raises(KeyLookupError):
        keyring.get_key("unknown")


def test_encrypt_rejects_non_bytes_aad() -> None:
    keyring = get_encryption_keyring()
    with pytest.raises(EncryptionFailedError):
        encrypt(b"value", aad="bad-aad", keyring=keyring)  # type: ignore[arg-type]
    with pytest.raises(EncryptionFailedError):
        encrypt(b"value", aad=None, keyring=keyring)  # type: ignore[arg-type]


def test_lifespan_calls_encryption_config(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(app):
        assert hasattr(app.state, "orphan_cleanup")
        assert not hasattr(app.state, "encryption_keyring")
        assert not hasattr(app.state, "encryption_config")
        assert app.state.orphan_cleanup["scanned_count"] >= 0

    monkeypatch.delenv("DATA_ENCRYPTION_KEYS_JSON", raising=False)
    with pytest.raises(EncryptionConfigurationError):
        with TestClient(app):
            pass
