from __future__ import annotations

import json
import logging
import re
import time
from typing import Any


_UNSAFE_LOG_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_SENSITIVE_EXTRA_KEYS = {
    "authorization", "cookie", "jwt", "token", "password", "secret", "api_key",
    "database_url", "db_url", "ciphertext", "nonce", "encryption_key", "hmac_key",
    "request_body", "response_body", "provider_request", "provider_response",
    "clause_body", "evidence", "summary", "email", "filename",
}
_CORE_FIELDS = {
    "timestamp", "level", "logger", "event", "service", "status", "request_id",
    "job_id", "worker_id", "attempt_count", "duration_ms", "safe_error_code",
}


def configure_logging(service: str) -> None:
    logger = logging.getLogger()
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger().setLevel(logging.INFO)
    for handler in logging.getLogger().handlers:
        handler.setFormatter(logging.Formatter("%(message)s"))

    app_logger = logging.getLogger(service)
    app_logger.setLevel(logging.INFO)


def _coerce_request_id(value: str | None) -> str:
    if not value:
        return str(int(time.time_ns()))
    return _sanitize_identifier(value, fallback=str(int(time.time_ns())))


def _sanitize_identifier(value: object, *, fallback: str = "unknown") -> str:
    cleaned = _UNSAFE_LOG_CHARS.sub("_", str(value)).strip("._-")[:64]
    return cleaned or fallback


def _log_level(level: str | None, *, event: str, status: str | int) -> str:
    if level and level.lower() in {"debug", "info", "warning", "error", "critical"}:
        return level.lower()
    if isinstance(status, int) or str(status).isdigit():
        status_code = int(status)
        if status_code >= 500:
            return "error"
        if status_code >= 400:
            return "warning"
    marker = f"{event} {status}".lower()
    if any(value in marker for value in ("fail", "error", "claim_lost", "not_ready")):
        return "error"
    return "info"


def log_event(
    *,
    logger: logging.Logger,
    event: str,
    service: str,
    status: str | int,
    level: str | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
    worker_id: str | None = None,
    attempt_count: int | None = None,
    duration_ms: int | None = None,
    safe_error_code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    resolved_level = _log_level(level, event=event, status=status)
    payload: dict[str, Any] = {
        "timestamp": int(time.time() * 1000),
        "level": resolved_level,
        "logger": logger.name,
        "event": _sanitize_identifier(event),
        "service": _sanitize_identifier(service),
        "status": status,
        "request_id": _coerce_request_id(request_id),
    }

    if job_id:
        payload["job_id"] = _sanitize_identifier(job_id)
    if worker_id:
        payload["worker_id"] = _sanitize_identifier(worker_id)
    if attempt_count is not None:
        payload["attempt_count"] = max(0, int(attempt_count))
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if safe_error_code:
        payload["safe_error_code"] = _sanitize_identifier(safe_error_code)
    if extra:
        for key, value in extra.items():
            safe_key = _sanitize_identifier(key)
            normalized_key = safe_key.lower()
            if normalized_key in _CORE_FIELDS or normalized_key in _SENSITIVE_EXTRA_KEYS:
                continue
            payload[safe_key] = (
                _sanitize_identifier(value) if isinstance(value, str) else value
            )

    logger.log(
        getattr(logging, resolved_level.upper()),
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
    )
