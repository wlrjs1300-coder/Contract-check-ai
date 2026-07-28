from __future__ import annotations

import base64
import json

import pytest

from backend.app.core.operations_config import (
    OperationsConfigurationError,
    validate_runtime_configuration,
)


def _production_env(monkeypatch) -> dict[str, str]:
    values = {
        "APP_ENV": "production",
        "JWT_SECRET": "production-jwt-secret-with-enough-unique-characters-123",
        "DATA_ENCRYPTION_ACTIVE_KEY_ID": "production-key-v1",
        "DATA_ENCRYPTION_KEYS_JSON": json.dumps(
            [{
                "key_id": "production-key-v1",
                "key": base64.b64encode(bytes(range(32))).decode(),
                "status": "active",
            }]
        ),
        "EMAIL_LOOKUP_HMAC_KEY": base64.b64encode(bytes(range(32, 64))).decode(),
        "CORS_ALLOWED_ORIGINS": "https://contracts.example.invalid",
        "DATABASE_URL": "postgresql://db.example.invalid/contracts",
        "DEBUG": "false",
        "UVICORN_RELOAD": "false",
        "ANALYSIS_PROVIDER": "unavailable",
        "MAX_UPLOAD_BYTES": str(20 * 1024 * 1024),
        "MAX_EXTRACTED_CHARACTERS": "2000000",
        "MAX_DOCUMENT_PAGES": "100",
        "RATE_LIMIT_LOGIN": "10",
        "RATE_LIMIT_REGISTER": "5",
        "RATE_LIMIT_UPLOAD": "10",
        "RATE_LIMIT_EXTRACTION": "20",
        "RATE_LIMIT_ANALYSIS_JOB": "10",
        "RATE_LIMIT_WINDOW_SECONDS": "60",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


@pytest.mark.parametrize(
    ("key", "value", "category"),
    [
        ("JWT_SECRET", "placeholder-placeholder-placeholder-00", "invalid_secret_config"),
        (
            "DATA_ENCRYPTION_KEYS_JSON",
            json.dumps([{
                "key_id": "production-key-v1",
                "key": base64.b64encode(b"x" * 32).decode(),
                "status": "active",
            }]),
            "invalid_secret_config",
        ),
        (
            "EMAIL_LOOKUP_HMAC_KEY",
            base64.b64encode(b"x" * 32).decode(),
            "invalid_secret_config",
        ),
        ("DATABASE_URL", "sqlite:///private-production.db", "invalid_database_config"),
        ("CORS_ALLOWED_ORIGINS", "*", "invalid_cors_config"),
        ("CORS_ALLOWED_ORIGINS", "http://localhost:5173", "invalid_cors_config"),
        ("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:5173", "invalid_cors_config"),
        ("DEBUG", "true", "invalid_debug_config"),
        ("UVICORN_RELOAD", "true", "invalid_debug_config"),
    ],
)
def test_production_rejects_unsafe_configuration(
    monkeypatch, key: str, value: str, category: str
) -> None:
    configured = _production_env(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(OperationsConfigurationError) as exc_info:
        validate_runtime_configuration()
    message = str(exc_info.value)
    assert category in message
    assert value not in message
    assert configured["DATABASE_URL"] not in message
    assert configured["CORS_ALLOWED_ORIGINS"] not in message
    assert configured["JWT_SECRET"] not in message


def test_unknown_app_env_is_rejected_without_echo(monkeypatch) -> None:
    _production_env(monkeypatch)
    unknown = "private-custom-environment"
    monkeypatch.setenv("APP_ENV", unknown)
    with pytest.raises(OperationsConfigurationError, match="invalid_app_env") as exc_info:
        validate_runtime_configuration()
    assert unknown not in str(exc_info.value)


def test_safe_production_configuration_passes(monkeypatch) -> None:
    _production_env(monkeypatch)
    validate_runtime_configuration()


@pytest.mark.parametrize("app_env", ["test", "development", ""])
def test_non_production_default_policy_is_preserved(monkeypatch, app_env: str) -> None:
    _production_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", app_env)
    validate_runtime_configuration()
