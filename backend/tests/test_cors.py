import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, parse_cors_allowed_origins


client = TestClient(app)


def test_default_frontend_origin_preflight_is_allowed() -> None:
    response = client.options(
        "/documents/upload",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )
    assert "POST" in response.headers["access-control-allow-methods"]
    assert (
        "content-type"
        in response.headers["access-control-allow-headers"].lower()
    )
    assert "access-control-allow-credentials" not in response.headers


def test_unlisted_origin_is_not_allowed() -> None:
    response = client.options(
        "/documents/upload",
        headers={
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_parse_cors_allowed_origins_accepts_multiple_origins() -> None:
    assert parse_cors_allowed_origins(
        "http://localhost:5173,https://frontend.example"
    ) == [
        "http://localhost:5173",
        "https://frontend.example",
    ]


def test_parse_cors_allowed_origins_reads_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,https://frontend.example",
    )

    assert parse_cors_allowed_origins() == [
        "http://localhost:5173",
        "https://frontend.example",
    ]


def test_parse_cors_allowed_origins_removes_spaces_empty_items_and_slashes(
) -> None:
    assert parse_cors_allowed_origins(
        " http://localhost:5173/ , , https://frontend.example/// "
    ) == [
        "http://localhost:5173",
        "https://frontend.example",
    ]


def test_parse_cors_allowed_origins_removes_duplicates_in_order() -> None:
    assert parse_cors_allowed_origins(
        "https://first.example,https://first.example,https://second.example"
    ) == [
        "https://first.example",
        "https://second.example",
    ]


def test_parse_cors_allowed_origins_allows_an_empty_deny_all_list() -> None:
    assert parse_cors_allowed_origins(" , ") == []


def test_parse_cors_allowed_origins_uses_safe_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert parse_cors_allowed_origins() == [
        "http://localhost:5173"
    ]
    assert "*" not in parse_cors_allowed_origins()


def test_parse_cors_allowed_origins_rejects_wildcard() -> None:
    with pytest.raises(
        ValueError,
        match="CORS wildcard origins are not allowed",
    ):
        parse_cors_allowed_origins("*")


def test_parse_cors_allowed_origins_rejects_mixed_wildcard() -> None:
    with pytest.raises(
        ValueError,
        match="CORS wildcard origins are not allowed",
    ):
        parse_cors_allowed_origins("http://localhost:5173,*")


def test_parse_cors_allowed_origins_rejects_paths() -> None:
    with pytest.raises(
        ValueError,
        match="CORS origins must be HTTP origins without paths",
    ):
        parse_cors_allowed_origins("https://frontend.example/app")


def test_health_check_remains_available() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
