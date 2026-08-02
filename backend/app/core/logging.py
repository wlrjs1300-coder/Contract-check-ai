from __future__ import annotations

import json
import logging
import math
import re
import time
from typing import Any
from uuid import uuid4

from backend.app.core.observability import metrics, record_event_metric


_UNSAFE_LOG_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_SENSITIVE_EXTRA_KEYS = {
    "authorization", "cookie", "jwt", "token", "password", "secret", "api_key",
    "access_token", "refresh_token", "credential", "private_key", "key_material",
    "database_url", "db_url", "ciphertext", "nonce", "encryption_key", "hmac_key",
    "request_body", "response_body", "provider_request", "provider_response",
    "clause_body", "evidence", "summary", "email", "filename",
    "forwarded", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host",
    "forwarded_chain", "client_ip", "peer_ip", "host",
}
_SENSITIVE_KEY_TOKENS = frozenset(
    re.sub(r"[^a-z0-9]", "", key.lower()) for key in _SENSITIVE_EXTRA_KEYS
) | {
    "userid", "resourceid", "documentid", "extractionid", "authorization",
    "accesstoken", "refreshtoken", "requestbody", "responsebody",
    "exception", "stacktrace", "localpath", "temppath", "artifactpath",
}
_CORE_FIELDS = {
    "timestamp", "level", "logger", "event", "service", "status", "request_id",
    "job_id", "worker_id", "attempt_count", "duration_ms", "safe_error_code",
    "event_id", "event_category", "severity", "outcome", "correlation_id",
    "actor_type", "actor_id", "target_type", "action_code", "status_code",
    "block_reason_code", "metric_key", "alert_candidate",
}
_EVENT_CATEGORIES = frozenset({"operational", "audit", "security"})
_SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})
_OUTCOMES = frozenset({"success", "failed", "denied", "blocked", "scheduled"})
_DROP_EXTRA_VALUE = object()


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


def _safe_extra_value(value: object) -> object:
    if value is None:
        return None
    if type(value) is str:
        return _sanitize_identifier(value)
    if type(value) in {int, bool}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return _DROP_EXTRA_VALUE


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
    event_category: str = "operational",
    severity: str | None = None,
    outcome: str | None = None,
    correlation_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    target_type: str | None = None,
    action_code: str | None = None,
    status_code: int | None = None,
    block_reason_code: str | None = None,
    alert_candidate: bool | None = None,
    collector: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    if event_category not in _EVENT_CATEGORIES:
        event_category = "operational"
    resolved_level = _log_level(level, event=event, status=status)
    resolved_severity = (
        severity.lower()
        if severity and severity.lower() in _SEVERITIES
        else resolved_level
    )
    payload: dict[str, Any] = {
        "timestamp": int(time.time() * 1000),
        "event_id": uuid4().hex,
        "level": resolved_level,
        "logger": logger.name,
        "event": _sanitize_identifier(event),
        "event_category": event_category,
        "service": _sanitize_identifier(service),
        "severity": resolved_severity,
        "status": status,
        "request_id": _coerce_request_id(request_id),
    }
    if outcome in _OUTCOMES:
        payload["outcome"] = outcome
    if correlation_id:
        payload["correlation_id"] = _sanitize_identifier(correlation_id)
    if actor_type:
        payload["actor_type"] = _sanitize_identifier(actor_type)
    if actor_id:
        payload["actor_id"] = _sanitize_identifier(actor_id)
    if target_type:
        payload["target_type"] = _sanitize_identifier(target_type)
    if action_code:
        payload["action_code"] = _sanitize_identifier(action_code)
    if status_code is not None:
        payload["status_code"] = int(status_code)
    if block_reason_code:
        payload["block_reason_code"] = _sanitize_identifier(block_reason_code)
    if alert_candidate is not None:
        payload["alert_candidate"] = bool(alert_candidate)

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
    metric_key = record_event_metric(payload["event"], status=status)
    if metric_key:
        payload["metric_key"] = metric_key
    if extra:
        for key, value in extra.items():
            if type(key) is not str:
                continue
            safe_key = _sanitize_identifier(key)
            normalized_key = safe_key.lower()
            compact_key = re.sub(r"[^a-z0-9]", "", normalized_key)
            if (
                normalized_key in _CORE_FIELDS
                or normalized_key in _SENSITIVE_EXTRA_KEYS
                or any(token in compact_key for token in _SENSITIVE_KEY_TOKENS)
            ):
                continue
            safe_value = _safe_extra_value(value)
            if safe_value is _DROP_EXTRA_VALUE:
                continue
            payload[safe_key] = safe_value

    try:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        if collector is not None:
            collector(dict(payload))
        logger.log(getattr(logging, resolved_level.upper()), encoded)
    except Exception:
        metrics.increment("event_delivery_failure_total")
        logging.getLogger("observability").error(
            '{"event":"event_delivery_failed","event_category":"operational"}'
        )
