from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import readiness
from backend.app.services.readiness import ReadinessError


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_check_readiness(monkeypatch) -> None:
    def unexpected_call():
        raise AssertionError("readiness must not run for liveness")

    monkeypatch.setattr("backend.app.main.get_readiness_status", unexpected_call)
    assert client.get("/health").status_code == 200


def test_ready_success_without_provider_call(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.main.get_readiness_status", lambda: {"status": "ready"}
    )
    monkeypatch.setattr(
        "backend.app.services.analysis_provider_factory.create_analysis_provider",
        lambda: (_ for _ in ()).throw(AssertionError("provider called")),
    )
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_database_failure_is_safe(monkeypatch) -> None:
    database_url = "postgresql://private-host.example.invalid/private-db"

    def unavailable():
        raise ReadinessError("database_unreachable") from RuntimeError(
            f"raw failure for {database_url}"
        )

    monkeypatch.setattr("backend.app.main.get_readiness_status", unavailable)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "private" not in response.text
    assert database_url not in response.text


def test_ready_migration_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.app.main.get_readiness_status",
        lambda: (_ for _ in ()).throw(ReadinessError("migration_head_mismatch")),
    )
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_readiness_internal_checks_are_independently_patchable(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        readiness,
        "_assert_database_connectivity",
        lambda url: calls.append(("database", url)),
    )
    monkeypatch.setattr(
        readiness,
        "_assert_alembic_head",
        lambda url: calls.append(("migration", url)),
    )
    assert readiness.get_readiness_status("postgresql://safe-host/db") == {
        "status": "ready"
    }
    assert calls == [
        ("database", "postgresql://safe-host/db"),
        ("migration", "postgresql://safe-host/db"),
    ]
