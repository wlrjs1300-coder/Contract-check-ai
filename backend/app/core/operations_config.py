from __future__ import annotations

import os
import re

from backend.app.core.config import get_jwt_config
from backend.app.core.boundary_config import get_boundary_config
from backend.app.core.email_lookup import get_email_lookup_key
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.services.analysis_provider_factory import create_analysis_provider


class OperationsConfigurationError(RuntimeError):
    """Raised when runtime operations configuration is invalid."""


def _safe_error(category: str) -> str:
    return f"Invalid runtime configuration: {category}."


def _normalize_app_env() -> str:
    return (os.getenv("APP_ENV", "test").strip().lower() or "test")


def _is_true_env_flag(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _parse_cors_allowed_origins(*, value: str | None = None) -> list[str]:
    configured_value = value if value is not None else os.getenv("CORS_ALLOWED_ORIGINS", "")
    if not configured_value:
        return []

    origins = [
        origin.strip().rstrip("/")
        for origin in configured_value.split(",")
        if origin.strip().rstrip("/")
    ]

    if "*" in origins:
        raise OperationsConfigurationError(_safe_error("invalid_cors_config"))

    for origin in origins:
        if not re.match(r"^https?://[^/\s]+(:\d+)?$", origin):
            raise OperationsConfigurationError(_safe_error("invalid_cors_config"))

    return list(dict.fromkeys(origins))


def _is_weak_ascii_secret(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    if len(set(stripped)) < 8:
        return True

    lowered = stripped.lower()
    if any(marker in lowered for marker in ("placeholder", "change-me", "changeme")):
        return True
    return lowered in {
        "secret",
        "change-me",
        "changeme",
        "password",
        "changeme123",
        "admin",
        "example",
        "default",
    }


def _is_weak_binary_value(value: bytes) -> bool:
    if not value:
        return True
    return len(set(value)) < 8


def _validate_secret_material() -> None:
    jwt_config = get_jwt_config()
    if _is_weak_ascii_secret(jwt_config.secret):
        raise OperationsConfigurationError(_safe_error("invalid_secret_config"))

    keyring = get_encryption_keyring()
    active_key = keyring.get_active_key()
    if _is_weak_binary_value(active_key.key):
        raise OperationsConfigurationError(_safe_error("invalid_secret_config"))

    email_lookup_key = get_email_lookup_key()
    if _is_weak_binary_value(email_lookup_key.key):
        raise OperationsConfigurationError(_safe_error("invalid_secret_config"))


def _validate_cors_for_production() -> None:
    cors_env = os.getenv("CORS_ALLOWED_ORIGINS")
    if cors_env is None:
        raise OperationsConfigurationError(_safe_error("invalid_cors_config"))

    origins = _parse_cors_allowed_origins(value=cors_env)
    if not origins:
        raise OperationsConfigurationError(_safe_error("invalid_cors_config"))

    for origin in origins:
        lowered = origin.lower()
        if lowered.startswith("http://localhost") or lowered.startswith("https://localhost"):
            raise OperationsConfigurationError(_safe_error("invalid_cors_config"))
        if lowered.startswith("http://127.") or lowered.startswith("https://127."):
            raise OperationsConfigurationError(_safe_error("invalid_cors_config"))
        if lowered.startswith("http://0.") or lowered.startswith("https://0."):
            raise OperationsConfigurationError(_safe_error("invalid_cors_config"))


def _validate_database_for_production() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise OperationsConfigurationError(_safe_error("invalid_database_config"))

    if database_url.strip().lower().startswith("sqlite"):
        raise OperationsConfigurationError(_safe_error("invalid_database_config"))


def _validate_debug_controls_for_production() -> None:
    if _is_true_env_flag(os.getenv("DEBUG")):
        raise OperationsConfigurationError(_safe_error("invalid_debug_config"))
    if _is_true_env_flag(os.getenv("UVICORN_RELOAD")):
        raise OperationsConfigurationError(_safe_error("invalid_debug_config"))


def _validate_provider_for_production() -> None:
    provider_name = (os.getenv("ANALYSIS_PROVIDER") or "").strip().lower()
    if not provider_name:
        raise OperationsConfigurationError(_safe_error("invalid_provider_config"))
    if provider_name in {"", "synthetic", "fake", "default", "not_configured", "real_placeholder"}:
        raise OperationsConfigurationError(_safe_error("invalid_provider_config"))

    provider = create_analysis_provider()
    if provider.provider_name not in {"unavailable", "real"}:
        raise OperationsConfigurationError(_safe_error("invalid_provider_config"))


def validate_runtime_configuration() -> None:
    app_env = _normalize_app_env()

    if app_env not in {"test", "development", "production", "prod"}:
        raise OperationsConfigurationError(_safe_error("invalid_app_env"))

    _ = get_jwt_config()
    _ = get_encryption_keyring()
    _ = get_email_lookup_key()

    if app_env in {"test", "development"}:
        return

    validators = (
        (_validate_secret_material, "invalid_secret_config"),
        (_validate_cors_for_production, "invalid_cors_config"),
        (_validate_database_for_production, "invalid_database_config"),
        (_validate_debug_controls_for_production, "invalid_debug_config"),
        (_validate_provider_for_production, "invalid_provider_config"),
        (get_boundary_config, "invalid_boundary_config"),
    )
    for validator, category in validators:
        try:
            validator()
        except OperationsConfigurationError:
            raise
        except Exception:
            raise OperationsConfigurationError(_safe_error(category)) from None
