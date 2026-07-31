from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.core.observability import (
    AlertCandidate,
    MetricRegistry,
    evaluate_synthetic_alerts,
)


def test_metric_registry_is_resettable_and_thread_safe() -> None:
    registry = MetricRegistry()
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(
            executor.map(
                lambda _: registry.increment("authentication_failure_total"),
                range(100),
            )
        )
    assert registry.snapshot()["authentication_failure_total"] == 100
    registry.reset()
    assert registry.snapshot()["authentication_failure_total"] == 0


@pytest.mark.parametrize(
    "metric_key",
    ["user_id", "email", "client_ip", "resource_id", "unbounded_label"],
)
def test_metric_registry_rejects_high_cardinality_or_unknown_keys(
    metric_key: str,
) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        MetricRegistry().increment(metric_key)


def test_synthetic_alert_thresholds_are_candidates_only() -> None:
    before = evaluate_synthetic_alerts({"authentication_failure_total": 2})
    after = evaluate_synthetic_alerts({"authentication_failure_total": 3})
    assert _find(before, "AUTHENTICATION_FAILURE_REPEATED").status == "clear"
    candidate = _find(after, "AUTHENTICATION_FAILURE_REPEATED")
    assert candidate.status == "candidate"
    assert candidate.observed_count == 3
    assert candidate.threshold_candidate == 3


def test_alert_output_has_only_fixed_safe_fields() -> None:
    candidate = evaluate_synthetic_alerts({"readiness_failure_total": 1})[0]
    assert set(candidate.__dict__) == {
        "alert_code",
        "status",
        "severity",
        "observed_count",
        "threshold_candidate",
    }


def _find(
    candidates: tuple[AlertCandidate, ...],
    code: str,
) -> AlertCandidate:
    return next(item for item in candidates if item.alert_code == code)
