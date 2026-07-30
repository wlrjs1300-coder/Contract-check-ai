from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from backend.app.core.auth import get_current_user
from backend.app.core.boundary_config import get_boundary_config
from backend.app.core.logging import log_event
from backend.app.core.proxy_config import get_proxy_config
from backend.app.core.request_context import build_client_context
from backend.app.db.models import User


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0


class InMemoryRateLimiter:
    """Process-local limiter. Buckets are intentionally not shared across replicas."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_buckets: int = 10_000,
    ) -> None:
        self._clock = clock
        self._max_buckets = max_buckets
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return RateLimitDecision(
                    allowed=False,
                    retry_after=max(1, math.ceil(bucket[0] + window_seconds - now)),
                )
            bucket.append(now)
            if len(self._buckets) > self._max_buckets:
                self._remove_expired(cutoff)
        return RateLimitDecision(allowed=True)

    def _remove_expired(self, cutoff: float) -> None:
        expired = [
            key
            for key, bucket in self._buckets.items()
            if not bucket or bucket[-1] <= cutoff
        ]
        for key in expired:
            self._buckets.pop(key, None)
        while len(self._buckets) > self._max_buckets:
            self._buckets.pop(next(iter(self._buckets)))

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    @property
    def bucket_count(self) -> int:
        with self._lock:
            return len(self._buckets)


rate_limiter = InMemoryRateLimiter()
_BUCKET_LIMIT_ATTRIBUTE = {
    "login": "rate_limit_login",
    "register": "rate_limit_register",
    "upload": "rate_limit_upload",
    "extraction": "rate_limit_extraction",
    "analysis_job": "rate_limit_analysis_job",
}


def _opaque_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject(request: Request, bucket: str, decision: RateLimitDecision) -> None:
    log_event(
        logger=logging.getLogger("api"),
        event="rate_limit_exceeded",
        service="api",
        status=429,
        request_id=getattr(request.state, "request_id", None),
        safe_error_code="RATE_LIMIT_EXCEEDED",
        extra={"rate_limit_bucket": bucket},
    )
    raise HTTPException(
        status_code=429,
        detail={
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
        },
        headers={"Retry-After": str(decision.retry_after)},
    )


def enforce_public_rate_limit(bucket: str):
    def dependency(request: Request) -> None:
        config = get_boundary_config()
        client_context = getattr(request.state, "client_context", None)
        if client_context is None:
            client_context = build_client_context(
                request,
                get_proxy_config(enforce_production=False),
            )
        key = f"{bucket}:{_opaque_key(client_context.client_ip)}"
        decision = rate_limiter.check(
            key,
            limit=getattr(config, _BUCKET_LIMIT_ATTRIBUTE[bucket]),
            window_seconds=config.rate_limit_window_seconds,
        )
        if not decision.allowed:
            _reject(request, bucket, decision)

    return dependency


def enforce_user_rate_limit(bucket: str):
    def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> None:
        config = get_boundary_config()
        key = f"{bucket}:{_opaque_key(current_user.id)}"
        decision = rate_limiter.check(
            key,
            limit=getattr(config, _BUCKET_LIMIT_ATTRIBUTE[bucket]),
            window_seconds=config.rate_limit_window_seconds,
        )
        if not decision.allowed:
            _reject(request, bucket, decision)

    return dependency
