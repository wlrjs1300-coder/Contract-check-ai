from __future__ import annotations

from fastapi.testclient import TestClient
import logging
import pytest
from starlette.requests import Request

from backend.app.core.proxy_config import get_proxy_config
from backend.app.core.request_context import (
    MAX_FORWARDED_HOPS,
    build_client_context,
)
from backend.app.main import app


def _proxy_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    trust: bool,
    require_https: bool = True,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", str(trust).lower())
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "192.0.2.0/24" if trust else "")
    monkeypatch.setenv("REQUIRE_HTTPS", str(require_https).lower())
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.invalid")


def test_untrusted_peer_forwarded_headers_do_not_change_scheme(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _proxy_env(monkeypatch, trust=True)
    client = TestClient(
        app,
        base_url="http://api.example.invalid",
        client=("198.51.100.10", 50000),
    )
    with caplog.at_level(logging.INFO):
        response = client.get(
            "/health",
            headers={
                "X-Forwarded-For": "203.0.113.8",
                "X-Forwarded-Proto": "https",
            },
        )
    assert response.status_code == 426
    assert response.json() == {"detail": "HTTPS is required."}
    rendered = "\n".join(record.message for record in caplog.records)
    assert "203.0.113.8" not in rendered
    assert "X-Forwarded-For" not in rendered


def test_trusted_proxy_uses_first_untrusted_candidate_from_right(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=True)
    client = TestClient(
        app,
        base_url="http://api.example.invalid",
        client=("192.0.2.10", 50000),
    )
    with client:
        request = client.build_request(
            "GET",
            "/health",
            headers={
                "X-Forwarded-For": "203.0.113.9, 198.51.100.7, 192.0.2.20",
                "X-Forwarded-Proto": "https",
            },
        )
        response = client.send(request)
    assert response.status_code == 200


def test_context_resolves_trusted_chain_without_exposing_raw_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=True)
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/health",
            "raw_path": b"/health",
            "query_string": b"",
            "headers": [
                (b"host", b"api.example.invalid"),
                (b"x-forwarded-for", b"203.0.113.9, 192.0.2.20"),
                (b"x-forwarded-proto", b"https"),
            ],
            "client": ("192.0.2.10", 50000),
            "server": ("app", 8000),
        }
    )
    context = build_client_context(request, get_proxy_config())
    assert context.peer_ip == "192.0.2.10"
    assert context.client_ip == "203.0.113.9"
    assert context.scheme == "https"
    assert context.forwarded_used


@pytest.mark.parametrize(
    "forwarded_for",
    [
        "not-an-ip",
        "203.0.113.9,,192.0.2.20",
        ",".join("203.0.113.9" for _ in range(MAX_FORWARDED_HOPS + 1)),
        "2" * 513,
    ],
)
def test_malformed_or_excessive_chain_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    forwarded_for: str,
) -> None:
    _proxy_env(monkeypatch, trust=True)
    client = TestClient(
        app,
        base_url="http://api.example.invalid",
        client=("192.0.2.10", 50000),
    )
    response = client.get(
        "/health",
        headers={
            "X-Forwarded-For": forwarded_for,
            "X-Forwarded-Proto": "https",
        },
    )
    assert response.status_code == 426


def test_direct_https_ignores_spoofed_forwarded_proto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=False)
    client = TestClient(
        app,
        base_url="https://api.example.invalid",
        client=("198.51.100.10", 50000),
    )
    response = client.get(
        "/health",
        headers={"X-Forwarded-Proto": "http"},
    )
    assert response.status_code == 200


def test_invalid_host_is_rejected_without_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=False)
    client = TestClient(
        app,
        base_url="https://unapproved.example.invalid",
        client=("198.51.100.10", 50000),
    )
    response = client.get(
        "/health",
        headers={
            "Forwarded": "for=203.0.113.8;proto=https;host=api.example.invalid",
            "X-Forwarded-Host": "api.example.invalid",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request host."}


def test_loopback_direct_health_remains_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=False)
    client = TestClient(
        app,
        base_url="http://internal.invalid",
        client=("127.0.0.1", 50000),
    )
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_loopback_trusted_proxy_health_does_not_bypass_host_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=True)
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "127.0.0.0/8")
    client = TestClient(
        app,
        base_url="http://unapproved.example.invalid",
        client=("127.0.0.1", 50000),
    )
    response = client.get(
        "/health",
        headers={
            "X-Forwarded-For": "203.0.113.8",
            "X-Forwarded-Proto": "https",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request host."}


def test_spoofed_forwarded_for_cannot_bypass_public_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=False)
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "1")
    client = TestClient(
        app,
        base_url="https://api.example.invalid",
        client=("198.51.100.10", 50000),
    )
    payload = {"email": "nobody@example.invalid", "password": "wrong-password"}
    first = client.post(
        "/auth/login",
        json=payload,
        headers={"X-Forwarded-For": "203.0.113.1"},
    )
    second = client.post(
        "/auth/login",
        json=payload,
        headers={"X-Forwarded-For": "203.0.113.2"},
    )
    assert first.status_code == 401
    assert second.status_code == 429


def test_trusted_proxy_separates_safe_client_rate_limit_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _proxy_env(monkeypatch, trust=True)
    monkeypatch.setenv("RATE_LIMIT_LOGIN", "1")
    client = TestClient(
        app,
        base_url="http://api.example.invalid",
        client=("192.0.2.10", 50000),
    )
    payload = {"email": "nobody@example.invalid", "password": "wrong-password"}
    for client_ip in ("203.0.113.1", "203.0.113.2"):
        response = client.post(
            "/auth/login",
            json=payload,
            headers={
                "X-Forwarded-For": client_ip,
                "X-Forwarded-Proto": "https",
            },
        )
        assert response.status_code == 401
