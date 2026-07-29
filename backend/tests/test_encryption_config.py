from __future__ import annotations

import base64
import json

import pytest

from backend.app.core.encryption_config import EncryptionConfigurationError, get_encryption_keyring


def _encode(seed: bytes) -> str:
    return base64.b64encode(seed).decode("ascii")


def _valid_payload(active_id: str = "synthetic-key-v1") -> str:
    return json.dumps(
        [
            {
                "key_id": active_id,
                "key": _encode(bytes(range(32))),
                "status": "active",
            },
            {
                "key_id": "synthetic-key-v0",
                "key": _encode(bytes(range(32, 64))),
                "status": "decrypt_only",
            },
        ]
    )


def _set_env(monkeypatch: pytest.MonkeyPatch, payload: str, active_id: str | None = "synthetic-key-v1") -> None:
    if payload is None:
        monkeypatch.delenv("DATA_ENCRYPTION_KEYS_JSON", raising=False)
    else:
        monkeypatch.setenv("DATA_ENCRYPTION_KEYS_JSON", payload)

    if active_id is None:
        monkeypatch.delenv("DATA_ENCRYPTION_ACTIVE_KEY_ID", raising=False)
    else:
        monkeypatch.setenv("DATA_ENCRYPTION_ACTIVE_KEY_ID", active_id)


def _assert_no_secret(text: str) -> None:
    for needle in ["x" * 32, "x" * 64, "AAECAw"]:
        assert needle not in text


def test_valid_keyring_parses_and_exposes_required_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_env(monkeypatch, _valid_payload())
    keyring = get_encryption_keyring()
    active = keyring.get_active_key()
    assert active.key_id == "synthetic-key-v1"
    assert active.status == "active"
    assert keyring.get_key("synthetic-key-v0").status == "decrypt_only"


@pytest.mark.parametrize(
    ("keys_json", "active_id"),
    [
        (None, "synthetic-key-v1"),
        ("", "synthetic-key-v1"),
        ("   ", "synthetic-key-v1"),
        ("not-json", "synthetic-key-v1"),
        ('{"k":"v"}', "synthetic-key-v1"),
        ("[]", "synthetic-key-v1"),
        (None, ""),
        (_valid_payload(active_id="synthetic-key-v1"), "unknown"),
        (_valid_payload(active_id="synthetic-key-v0"), "synthetic-key-v0"),
    ],
)
def test_keyring_rejects_invalid_config(
    monkeypatch: pytest.MonkeyPatch, keys_json: str | None, active_id: str
) -> None:
    _set_env(monkeypatch, keys_json, active_id)
    with pytest.raises(EncryptionConfigurationError) as exc:
        get_encryption_keyring()
    _assert_no_secret(str(exc.value))


@pytest.mark.parametrize(
    "item",
    [
        1,
        True,
        "string",
        {},
        {"key_id": "A-key", "key": "AAAA", "status": "active"},
        {"key_id": "synthetic_key_v1", "key": "AAAA", "status": "active"},
        {"key_id": "synthetic-key-v1", "key": 1, "status": "active"},
        {"key_id": "synthetic-key-v1", "status": "active"},
        {"key_id": "synthetic-key-v1", "key": "AAAA", "status": "active", "x": 1},
        {"key_id": "", "key": "AAAA", "status": "active"},
        {"key_id": "synthetic-key-v1", "key": "AAAA", "status": "retired"},
        {"key_id": "synthetic-key-v1", "key": "@@@@", "status": "active"},
        {"key_id": "synthetic-key-v1", "key": _encode(b"0" * 31), "status": "active"},
        {"key_id": "synthetic-key-v1", "key": _encode(b"0" * 33), "status": "active"},
        {"key_id": "synthetic-key-v1", "key": _encode(b"0" * 32), "status": "active", "key_id_alias": "x"},
    ],
)
def test_key_item_invalid(monkeypatch: pytest.MonkeyPatch, item: object) -> None:
    _set_env(monkeypatch, json.dumps([item]))
    monkeypatch.setenv("DATA_ENCRYPTION_ACTIVE_KEY_ID", "synthetic-key-v1")
    with pytest.raises(EncryptionConfigurationError):
        get_encryption_keyring()


def test_duplicate_and_active_count_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicate = [
        {
            "key_id": "synthetic-key-v1",
            "key": _encode(bytes(range(32))),
            "status": "active",
        },
        {
            "key_id": "synthetic-key-v1",
            "key": _encode(bytes(range(32, 64))),
            "status": "decrypt_only",
        },
    ]
    _set_env(monkeypatch, json.dumps(duplicate), "synthetic-key-v1")
    with pytest.raises(EncryptionConfigurationError):
        get_encryption_keyring()

    no_active = [
        {
            "key_id": "synthetic-key-v1",
            "key": _encode(bytes(range(32))),
            "status": "decrypt_only",
        },
        {
            "key_id": "synthetic-key-v0",
            "key": _encode(bytes(range(32, 64))),
            "status": "decrypt_only",
        },
    ]
    _set_env(monkeypatch, json.dumps(no_active), "synthetic-key-v1")
    with pytest.raises(EncryptionConfigurationError):
        get_encryption_keyring()

    too_many_active = [
        {
            "key_id": "synthetic-key-v1",
            "key": _encode(bytes(range(32))),
            "status": "active",
        },
        {
            "key_id": "synthetic-key-v0",
            "key": _encode(bytes(range(32, 64))),
            "status": "active",
        },
    ]
    _set_env(monkeypatch, json.dumps(too_many_active), "synthetic-key-v1")
    with pytest.raises(EncryptionConfigurationError):
        get_encryption_keyring()
