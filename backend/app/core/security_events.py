from __future__ import annotations

from collections.abc import Callable
import hashlib
import logging
from typing import Protocol

from backend.app.core.logging import log_event


_ACTOR_TYPES = frozenset({"authenticated_user", "anonymous", "system", "worker"})


def derive_actor_id(identifier: object) -> str:
    if not isinstance(identifier, str) or not identifier.strip():
        return "unknown"
    digest = hashlib.sha256(
        f"contract-check:audit-actor:v1:{identifier}".encode("utf-8")
    ).hexdigest()
    return f"actor_{digest[:24]}"


class EventCollector(Protocol):
    def __call__(self, event: dict[str, object]) -> None: ...


class InMemoryEventCollector:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def __call__(self, event: dict[str, object]) -> None:
        self.events.append(dict(event))


def emit_security_event(
    *,
    event: str,
    event_category: str,
    outcome: str,
    request_id: str | None,
    actor_type: str,
    actor_identifier: str | None = None,
    service: str = "api",
    severity: str | None = None,
    target_type: str | None = None,
    action_code: str | None = None,
    status_code: int | None = None,
    safe_error_code: str | None = None,
    block_reason_code: str | None = None,
    alert_candidate: bool | None = None,
    collector: EventCollector | Callable[[dict[str, object]], None] | None = None,
) -> None:
    resolved_actor_type = actor_type if actor_type in _ACTOR_TYPES else "system"
    actor_id = (
        derive_actor_id(actor_identifier)
        if resolved_actor_type == "authenticated_user"
        else None
    )
    log_event(
        logger=logging.getLogger(service),
        event=event,
        service=service,
        status=status_code if status_code is not None else outcome,
        request_id=request_id,
        event_category=event_category,
        severity=severity,
        outcome=outcome,
        actor_type=resolved_actor_type,
        actor_id=actor_id,
        target_type=target_type,
        action_code=action_code,
        status_code=status_code,
        safe_error_code=safe_error_code,
        block_reason_code=block_reason_code,
        alert_candidate=alert_candidate,
        collector=collector,
    )


def log_access_not_granted(
    *,
    request_id: str | None,
    user_id: str,
    target_type: str,
    action_code: str,
) -> None:
    emit_security_event(
        event="resource_access_not_granted",
        event_category="security",
        outcome="denied",
        request_id=request_id,
        actor_type="authenticated_user",
        actor_identifier=user_id,
        target_type=target_type,
        action_code=action_code,
        status_code=404,
        safe_error_code="RESOURCE_ACCESS_NOT_GRANTED",
    )
