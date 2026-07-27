from __future__ import annotations

from datetime import datetime, timedelta
from threading import Event

from fastapi.testclient import TestClient

from backend.app.db.models import AnalysisJob
from backend.app.main import app
from backend.app.services.analysis_job_queue import (
    claim_next_job,
    finish_job_failure,
    finish_job_success,
    recover_stale_jobs,
    renew_job_lease,
    retry_delay_seconds,
)
from backend.app.services.provider_execution import ProviderTimeoutError
from backend.app.workers.analysis_worker import WorkerConfig, run_worker
from conftest import TestingSessionLocal


client = TestClient(app)


def _pending_job() -> tuple[str, str]:
    upload = client.post(
        "/documents/upload",
        files={"file": ("durable.txt", "1. Durable analysis clause.", "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]
    response = client.post(f"/documents/{document_id}/analysis-jobs")
    assert response.status_code == 200
    return response.json()["job_id"], document_id


def test_create_analysis_job_returns_before_pipeline_execution() -> None:
    job_id, _ = _pending_job()
    with TestingSessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        assert job.status == "pending"
        assert not job.result_items


def test_duplicate_active_request_returns_existing_job() -> None:
    job_id, document_id = _pending_job()
    duplicate = client.post(f"/documents/{document_id}/analysis-jobs")
    assert duplicate.status_code == 200
    assert duplicate.json()["job_id"] == job_id


def test_completed_job_does_not_block_new_request() -> None:
    job_id, document_id = _pending_job()
    with TestingSessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        job.status = "completed"
        job.active_dedupe_key = None
        db.commit()
    replacement = client.post(f"/documents/{document_id}/analysis-jobs")
    assert replacement.json()["job_id"] != job_id


def test_worker_atomically_claims_pending_job_once() -> None:
    job_id, _ = _pending_job()
    now = datetime.utcnow()
    with TestingSessionLocal() as db:
        first = claim_next_job(
            db, worker_id="worker-a", lease_seconds=120, now=now
        )
    with TestingSessionLocal() as db:
        second = claim_next_job(
            db, worker_id="worker-b", lease_seconds=120, now=now
        )
    assert first is not None and first.id == job_id
    assert second is None


def test_worker_does_not_claim_future_or_exhausted_job() -> None:
    job_id, _ = _pending_job()
    with TestingSessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        job.available_at = datetime.utcnow() + timedelta(minutes=5)
        db.commit()
        assert claim_next_job(db, worker_id="worker-a", lease_seconds=120) is None
        job.available_at = datetime.utcnow() - timedelta(seconds=1)
        job.attempt_count = job.max_attempts
        db.commit()
        assert claim_next_job(db, worker_id="worker-a", lease_seconds=120) is None


def test_claim_sets_attempt_worker_lease_and_started_at() -> None:
    _pending_job()
    now = datetime.utcnow()
    with TestingSessionLocal() as db:
        job = claim_next_job(
            db, worker_id="worker-a", lease_seconds=120, now=now
        )
        assert job is not None
        assert job.status == "running"
        assert job.attempt_count == 1
        assert job.worker_id == "worker-a"
        assert job.started_at == now
        assert job.heartbeat_at == now
        assert job.lease_expires_at == now + timedelta(seconds=120)


def test_worker_renews_only_own_running_job_lease() -> None:
    job_id, _ = _pending_job()
    with TestingSessionLocal() as db:
        claim_next_job(db, worker_id="worker-a", lease_seconds=120)
    now = datetime.utcnow()
    with TestingSessionLocal() as db:
        assert not renew_job_lease(
            db,
            job_id=job_id,
            worker_id="worker-b",
            lease_seconds=120,
            now=now,
        )
        assert renew_job_lease(
            db,
            job_id=job_id,
            worker_id="worker-a",
            lease_seconds=120,
            now=now,
        )


def test_terminal_job_heartbeat_is_rejected() -> None:
    job_id, _ = _pending_job()
    with TestingSessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        job.status = "completed"
        db.commit()
        assert not renew_job_lease(
            db, job_id=job_id, worker_id="worker-a", lease_seconds=120
        )


def test_expired_running_job_is_requeued() -> None:
    job_id, _ = _pending_job()
    now = datetime.utcnow()
    with TestingSessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        job.status = "running"
        job.worker_id = "dead-worker"
        job.attempt_count = 1
        job.lease_expires_at = now - timedelta(seconds=1)
        db.commit()
        assert recover_stale_jobs(db, now=now) == 1
        db.refresh(job)
        assert job.status == "pending"
        assert job.last_error_code == "worker_lease_expired"


def test_expired_running_job_fails_after_max_attempts() -> None:
    job_id, _ = _pending_job()
    now = datetime.utcnow()
    with TestingSessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        job.status = "running"
        job.worker_id = "dead-worker"
        job.attempt_count = job.max_attempts
        job.lease_expires_at = now - timedelta(seconds=1)
        db.commit()
        assert recover_stale_jobs(db, now=now) == 1
        db.refresh(job)
        assert job.status == "failed"
        assert job.active_dedupe_key is None
        assert job.last_error_code == "max_attempts_exceeded"


def test_retryable_provider_error_schedules_retry_without_raw_message() -> None:
    job_id, _ = _pending_job()
    now = datetime.utcnow()
    with TestingSessionLocal() as db:
        claim_next_job(db, worker_id="worker-a", lease_seconds=120, now=now)
        outcome = finish_job_failure(
            db,
            job_id=job_id,
            worker_id="worker-a",
            error=ProviderTimeoutError("contract plaintext must not persist"),
            now=now,
            jitter=lambda _low, _high: 0,
        )
        job = db.get(AnalysisJob, job_id)
        assert outcome == "pending"
        assert job is not None
        assert job.available_at == now + timedelta(seconds=5)
        assert "contract plaintext" not in (job.last_error_message_safe or "")


def test_non_retryable_error_fails_immediately() -> None:
    job_id, _ = _pending_job()
    with TestingSessionLocal() as db:
        claim_next_job(db, worker_id="worker-a", lease_seconds=120)
        assert (
            finish_job_failure(
                db,
                job_id=job_id,
                worker_id="worker-a",
                error=ValueError("sensitive source"),
            )
            == "failed"
        )
        job = db.get(AnalysisJob, job_id)
        assert job is not None
        assert job.last_error_code == "analysis_execution_failed"
        assert "sensitive source" not in (job.last_error_message_safe or "")


def test_retry_backoff_is_bounded() -> None:
    assert retry_delay_seconds(1, jitter=lambda _a, _b: 0) == 5
    assert retry_delay_seconds(2, jitter=lambda _a, _b: 0) == 30
    assert retry_delay_seconds(99, jitter=lambda _a, b: b) == 120


def test_completed_job_clears_active_dedupe_key() -> None:
    _pending_job()
    with TestingSessionLocal() as db:
        job = claim_next_job(db, worker_id="worker-a", lease_seconds=120)
        assert job is not None
        finish_job_success(db, job=job, worker_id="worker-a")
        assert job.status == "completed"
        assert job.active_dedupe_key is None


def test_worker_shutdown_stops_polling() -> None:
    stop = Event()
    stop.set()
    run_worker(
        config=WorkerConfig(
            worker_id="worker-a",
            poll_seconds=0.01,
            lease_seconds=2,
            heartbeat_seconds=1,
        ),
        stop_event=stop,
    )


def test_job_status_response_does_not_expose_worker_metadata() -> None:
    job_id, _ = _pending_job()
    response = client.get(f"/analysis-jobs/{job_id}")
    assert response.status_code == 200
    assert set(response.json()) == {"job_id", "document_id", "status"}
