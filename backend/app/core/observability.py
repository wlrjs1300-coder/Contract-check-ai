from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import threading
from typing import Final


METRIC_KEYS: Final = frozenset(
    {
        "api_requests_total",
        "api_errors_total",
        "authentication_success_total",
        "authentication_failure_total",
        "authorization_not_granted_total",
        "rate_limit_block_total",
        "readiness_failure_total",
        "worker_completed_total",
        "worker_retry_total",
        "worker_terminal_failure_total",
        "worker_stale_recovery_total",
        "cleanup_failure_total",
        "event_delivery_failure_total",
    }
)

_EVENT_METRICS: Final = {
    "authentication_succeeded": "authentication_success_total",
    "authentication_failed": "authentication_failure_total",
    "resource_access_not_granted": "authorization_not_granted_total",
    "rate_limit_exceeded": "rate_limit_block_total",
    "readiness_failed": "readiness_failure_total",
    "analysis_job_completed": "worker_completed_total",
    "analysis_job_retry_scheduled": "worker_retry_total",
    "analysis_job_failed_terminal": "worker_terminal_failure_total",
    "analysis_job_stale_recovered": "worker_stale_recovery_total",
    "analysis_job_stale_failed": "worker_terminal_failure_total",
    "temporary_cleanup_failed": "cleanup_failure_total",
    "orphan_cleanup_failed": "cleanup_failure_total",
    "orphan_cleanup_unsafe_skipped": "cleanup_failure_total",
}


class MetricRegistry:
    """Thread-safe, process-local counters; no multi-replica aggregation."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def increment(self, metric_key: str, value: int = 1) -> None:
        if metric_key not in METRIC_KEYS:
            raise ValueError("Metric key is not allowed.")
        if type(value) is not int or value < 0:
            raise ValueError("Metric increment must be a non-negative integer.")
        with self._lock:
            self._counts[metric_key] += value

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {key: self._counts.get(key, 0) for key in sorted(METRIC_KEYS)}

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


metrics = MetricRegistry()


def record_event_metric(event: str, *, status: str | int) -> str | None:
    metric_key = _EVENT_METRICS.get(event)
    if metric_key is not None:
        metrics.increment(metric_key)
    if event == "http_request_completed":
        metrics.increment("api_requests_total")
        status_text = str(status)
        if status_text == "error" or (
            status_text.isdigit() and int(status_text) >= 500
        ):
            metrics.increment("api_errors_total")
    return metric_key


@dataclass(frozen=True)
class AlertCandidate:
    alert_code: str
    status: str
    severity: str
    observed_count: int
    threshold_candidate: int


SYNTHETIC_THRESHOLDS: Final = {
    "READINESS_FAILURE": ("readiness_failure_total", 1, "error"),
    "CLEANUP_FAILURE": ("cleanup_failure_total", 1, "error"),
    "WORKER_TERMINAL_FAILURE": ("worker_terminal_failure_total", 1, "error"),
    "WORKER_STALE_RECOVERY_REPEATED": ("worker_stale_recovery_total", 2, "warning"),
    "AUTHENTICATION_FAILURE_REPEATED": ("authentication_failure_total", 3, "warning"),
    "RATE_LIMIT_BLOCK_REPEATED": ("rate_limit_block_total", 3, "warning"),
    "API_5XX_REPEATED": ("api_errors_total", 3, "error"),
}


def evaluate_synthetic_alerts(snapshot: dict[str, int]) -> tuple[AlertCandidate, ...]:
    """Evaluate rehearsal-only candidates; thresholds are not production approved."""
    candidates = []
    for alert_code, (metric_key, threshold, severity) in SYNTHETIC_THRESHOLDS.items():
        observed = snapshot.get(metric_key, 0)
        if type(observed) is not int or observed < 0:
            raise ValueError("Metric snapshot contains an invalid value.")
        candidates.append(
            AlertCandidate(
                alert_code=alert_code,
                status="candidate" if observed >= threshold else "clear",
                severity=severity,
                observed_count=observed,
                threshold_candidate=threshold,
            )
        )
    return tuple(candidates)
