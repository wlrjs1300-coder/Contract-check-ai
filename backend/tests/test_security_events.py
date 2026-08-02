from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import json
import logging
import math

from backend.app.core.logging import log_event
from backend.app.core.observability import metrics
from backend.app.core.security_events import (
    InMemoryEventCollector,
    derive_actor_id,
    emit_security_event,
)


def test_actor_identifier_is_stable_bounded_and_non_reversible() -> None:
    source = "00000000-0000-4000-8000-000000000123"
    derived = derive_actor_id(source)
    assert derived == derive_actor_id(source)
    assert derived.startswith("actor_")
    assert len(derived) == 30
    assert source not in derived
    assert derive_actor_id("") == "unknown"
    assert derive_actor_id(None) == "unknown"


def test_security_event_schema_is_json_serializable_and_correlated(
    caplog,
) -> None:
    collector = InMemoryEventCollector()
    with caplog.at_level(logging.INFO, logger="api"):
        emit_security_event(
            event="authentication_succeeded",
            event_category="audit",
            outcome="success",
            request_id="synthetic-request",
            actor_type="authenticated_user",
            actor_identifier="00000000-0000-4000-8000-000000000123",
            action_code="login",
            status_code=200,
            collector=collector,
        )

    payload = collector.events[0]
    assert payload["event_category"] == "audit"
    assert payload["severity"] == "info"
    assert payload["outcome"] == "success"
    assert payload["request_id"] == "synthetic-request"
    assert len(payload["event_id"]) == 32
    assert payload["actor_id"].startswith("actor_")
    json.dumps(payload)
    assert json.loads(caplog.records[-1].message) == payload


def test_unknown_category_and_schema_values_are_fail_closed() -> None:
    collector = InMemoryEventCollector()
    emit_security_event(
        event="synthetic_event",
        event_category="not-allowed",
        outcome="not-allowed",
        request_id="synthetic-request",
        actor_type="not-allowed",
        collector=collector,
    )
    payload = collector.events[0]
    assert payload["event_category"] == "operational"
    assert payload["actor_type"] == "system"
    assert "outcome" not in payload


def test_sensitive_extra_key_variants_and_core_overrides_are_dropped() -> None:
    collector = InMemoryEventCollector()
    log_event(
        logger=logging.getLogger("api"),
        event="synthetic_event",
        service="api",
        status="success",
        collector=collector,
        extra={
            "Authorization": "forbidden",
            "x_authorization": "forbidden",
            "access-token": "forbidden",
            "access_token": "forbidden",
            "raw_exception": "forbidden",
            "document-id": "forbidden",
            "event_category": "security",
            "safe_count": 2,
        },
    )
    payload = collector.events[0]
    assert payload["event_category"] == "operational"
    assert payload["safe_count"] == 2
    assert "forbidden" not in json.dumps(payload)


def test_nested_and_non_scalar_extra_values_are_dropped() -> None:
    class UnsafeEnum(IntEnum):
        VALUE = 1

    @dataclass
    class UnsafeDataclass:
        value: str

    class UnsafeObject:
        def __str__(self) -> str:
            raise AssertionError("Unsafe objects must not be stringified.")

    collector = InMemoryEventCollector()
    forbidden_values = {
        "nested": {
            "email": "person@example.invalid",
            "filename": "private.pdf",
        },
        "items": ["raw-token", "contract body"],
        "tuple_value": ("raw-token",),
        "set_value": {"raw-token"},
        "bytes_value": b"raw-token",
        "bytearray_value": bytearray(b"raw-token"),
        "exception_value": RuntimeError("raw exception"),
        "enum_value": UnsafeEnum.VALUE,
        "dataclass_value": UnsafeDataclass("private data"),
        "object_value": UnsafeObject(),
    }
    log_event(
        logger=logging.getLogger("api"),
        event="synthetic_event",
        service="api",
        status="success",
        collector=collector,
        extra=forbidden_values,
    )
    payload = collector.events[0]
    rendered = json.dumps(payload)
    for key in forbidden_values:
        assert key not in payload
    for forbidden in (
        "person@example.invalid",
        "private.pdf",
        "raw-token",
        "contract body",
        "raw exception",
        "private data",
    ):
        assert forbidden not in rendered


def test_non_finite_float_extra_values_are_dropped() -> None:
    collector = InMemoryEventCollector()
    log_event(
        logger=logging.getLogger("api"),
        event="synthetic_event",
        service="api",
        status="success",
        collector=collector,
        extra={
            "nan_value": math.nan,
            "positive_infinity": math.inf,
            "negative_infinity": -math.inf,
        },
    )
    payload = collector.events[0]
    assert "nan_value" not in payload
    assert "positive_infinity" not in payload
    assert "negative_infinity" not in payload
    assert "NaN" not in json.dumps(payload)
    assert "Infinity" not in json.dumps(payload)


def test_safe_scalar_extra_values_and_existing_call_fields_are_preserved() -> None:
    collector = InMemoryEventCollector()
    log_event(
        logger=logging.getLogger("api"),
        event="synthetic_event",
        service="api",
        status="success",
        collector=collector,
        extra={
            "file_size": 1024,
            "content_type_category": "text/plain",
            "rate_limit_bucket": "login",
            "enabled": True,
            "ratio": 1.25,
            "optional": None,
        },
    )
    payload = collector.events[0]
    assert payload["file_size"] == 1024
    assert payload["content_type_category"] == "text_plain"
    assert payload["rate_limit_bucket"] == "login"
    assert payload["enabled"] is True
    assert payload["ratio"] == 1.25
    assert payload["optional"] is None


def test_collector_failure_is_detected_without_raising() -> None:
    metrics.reset()

    def broken_collector(_event: dict[str, object]) -> None:
        raise RuntimeError("sensitive raw error")

    emit_security_event(
        event="synthetic_event",
        event_category="security",
        outcome="failed",
        request_id=None,
        actor_type="system",
        collector=broken_collector,
    )
    assert metrics.snapshot()["event_delivery_failure_total"] == 1
