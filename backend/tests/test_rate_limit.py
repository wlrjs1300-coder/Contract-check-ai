from __future__ import annotations

from backend.app.core.rate_limit import InMemoryRateLimiter


def test_limiter_allows_limit_then_returns_retry_after() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    assert limiter.check("login:a", limit=2, window_seconds=60).allowed
    assert limiter.check("login:a", limit=2, window_seconds=60).allowed
    rejected = limiter.check("login:a", limit=2, window_seconds=60)
    assert not rejected.allowed
    assert rejected.retry_after == 60


def test_limiter_separates_identity_and_bucket() -> None:
    limiter = InMemoryRateLimiter(clock=lambda: 100.0)
    assert limiter.check("login:a", limit=1, window_seconds=60).allowed
    assert limiter.check("login:b", limit=1, window_seconds=60).allowed
    assert limiter.check("upload:a", limit=1, window_seconds=60).allowed


def test_limiter_expires_and_cleans_buckets() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0], max_buckets=2)
    limiter.check("a", limit=1, window_seconds=10)
    limiter.check("b", limit=1, window_seconds=10)
    now[0] = 111.0
    assert limiter.check("c", limit=1, window_seconds=10).allowed
    assert limiter.bucket_count <= 2
    assert limiter.check("a", limit=1, window_seconds=10).allowed


def test_login_endpoint_returns_safe_429(client, monkeypatch, caplog) -> None:
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "1")
    payload = {"email": "nobody@example.invalid", "password": "wrong-password"}
    assert client.post("/auth/login", json=payload).status_code == 401
    response = client.post(
        "/auth/login",
        json=payload,
        headers={"Authorization": "Bearer private-token"},
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json() == {
        "detail": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
        }
    }
    assert "private-token" not in response.text
    rate_limit_logs = [
        record.message
        for record in caplog.records
        if "rate_limit_exceeded" in record.message
    ]
    assert rate_limit_logs
    assert "RATE_LIMIT_EXCEEDED" in rate_limit_logs[-1]
    assert "private-token" not in rate_limit_logs[-1]
    assert "nobody@example.invalid" not in rate_limit_logs[-1]
