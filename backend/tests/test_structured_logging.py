from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from backend.app.db.models import AnalysisJob
from backend.app.main import app
from backend.app.core.logging import log_event
from backend.app.services.analysis_job_queue import claim_next_job
from backend.app.services.provider_execution import ProviderTimeoutError
from backend.app.workers.analysis_worker import WorkerConfig, process_job
from conftest import TestingSessionLocal


def _payload(caplog, **overrides):
    values = {
        "logger": logging.getLogger("structured-test"),
        "event": "analysis_completed",
        "service": "worker",
        "status": "completed",
        "request_id": "request-1",
    }
    values.update(overrides)
    with caplog.at_level(logging.INFO):
        log_event(**values)
    return json.loads(caplog.records[-1].message)


def test_json_fields_level_attempt_and_identifier_sanitization(caplog) -> None:
    payload = _payload(
        caplog,
        event="analysis_failure\nforged",
        status="failed",
        request_id="request\r\nforged",
        job_id="job/\x00private",
        worker_id="worker\tprivate",
        attempt_count=7,
        safe_error_code="provider timeout\n",
    )
    assert {"timestamp", "level", "logger", "event", "service", "status", "request_id"} <= payload.keys()
    assert payload["level"] == "error"
    assert payload["attempt_count"] == 7
    for key in ("event", "request_id", "job_id", "worker_id", "safe_error_code"):
        assert "\n" not in payload[key] and "\r" not in payload[key] and "\x00" not in payload[key]


def test_extra_cannot_override_core_or_emit_sensitive_values(caplog) -> None:
    secrets = {
        "authorization": "Bearer raw-jwt",
        "jwt": "raw-jwt",
        "token": "raw-token",
        "access_token": "raw-access-token",
        "refresh_token": "raw-refresh-token",
        "credential": "raw-credential",
        "private_key": "raw-private-key",
        "key_material": "raw-key-material",
        "database_url": "postgresql://private",
        "email": "person@example.invalid",
        "filename": "private-contract.pdf",
        "request_body": "raw contract",
        "x-forwarded-for": "203.0.113.9, 192.0.2.10",
        "x-forwarded-proto": "https",
        "forwarded": "for=203.0.113.9;proto=https",
        "client_ip": "203.0.113.9",
        "peer_ip": "192.0.2.10",
    }
    payload = _payload(
        caplog,
        extra={
            "timestamp": "forged",
            "level": "critical",
            "event": "forged",
            "service": "forged",
            "status": "forged",
            "request_id": "forged",
            **secrets,
        },
    )
    assert payload["level"] == "info"
    assert payload["event"] == "analysis_completed"
    assert payload["service"] == "worker"
    assert payload["status"] == "completed"
    assert payload["request_id"] == "request-1"
    rendered = json.dumps(payload)
    for key, value in secrets.items():
        assert key not in payload
        assert value not in rendered


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (ProviderTimeoutError("raw provider exception must not appear"), "pending"),
        (ValueError("raw execution exception must not appear"), "failed"),
    ],
)
def test_worker_failure_log_matches_persisted_safe_error(
    monkeypatch, failure: Exception, expected_status: str
) -> None:
    client = TestClient(app)
    upload = client.post(
        "/documents/upload",
        files={"file": ("safe.txt", "1. Safe clause.", "text/plain")},
    )
    job_id = client.post(
        f"/documents/{upload.json()['document_id']}/analysis-jobs"
    ).json()["job_id"]
    with TestingSessionLocal() as db:
        claimed = claim_next_job(db, worker_id="worker-safe", lease_seconds=120)
        assert claimed is not None
        attempt_count = claimed.attempt_count

    captured: list[dict[str, object]] = []
    monkeypatch.setattr(
        "backend.app.workers.analysis_worker.run_analysis_pipeline",
        lambda **_kwargs: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        "backend.app.workers.analysis_worker.create_analysis_provider", object
    )
    monkeypatch.setattr(
        "backend.app.workers.analysis_worker.SessionLocal", TestingSessionLocal
    )
    monkeypatch.setattr(
        "backend.app.workers.analysis_worker.log_event",
        lambda **kwargs: captured.append(kwargs),
    )
    assert process_job(
        job_id,
        WorkerConfig(
            worker_id="worker-safe",
            lease_seconds=2,
            heartbeat_seconds=1,
        ),
    ) == expected_status
    with TestingSessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        assert captured[-1]["status"] == expected_status
        assert captured[-1]["attempt_count"] == attempt_count
        assert captured[-1]["safe_error_code"] == job.last_error_code
        assert str(failure) not in str(captured[-1])
