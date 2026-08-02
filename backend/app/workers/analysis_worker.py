from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import time
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from backend.app.core.logging import configure_logging, log_event
from backend.app.db.database import SessionLocal
from backend.app.db.models import AnalysisJob, AnalysisResultItem, Document
from backend.app.services.analysis_job_queue import (
    claim_next_job,
    finish_job_failure,
    finish_job_success,
    recover_stale_jobs_result,
    renew_job_lease,
)
from backend.app.services.analysis_pipeline import run_analysis_pipeline
from backend.app.services.analysis_provider_factory import create_analysis_provider


logger = logging.getLogger("worker")


@dataclass(frozen=True)
class WorkerConfig:
    worker_id: str
    poll_seconds: float = 1.0
    lease_seconds: float = 120.0
    heartbeat_seconds: float = 30.0
    max_attempts: int = 3

    def validate(self) -> None:
        if self.poll_seconds <= 0:
            raise ValueError("ANALYSIS_WORKER_POLL_SECONDS must be greater than zero.")
        if self.heartbeat_seconds <= 0:
            raise ValueError("ANALYSIS_JOB_HEARTBEAT_SECONDS must be greater than zero.")
        if self.lease_seconds <= self.heartbeat_seconds:
            raise ValueError("ANALYSIS_JOB_LEASE_SECONDS must exceed heartbeat seconds.")
        if self.max_attempts < 1:
            raise ValueError("ANALYSIS_JOB_MAX_ATTEMPTS must be at least one.")
        if not self.worker_id.strip():
            raise ValueError("ANALYSIS_WORKER_ID must not be blank.")


def load_worker_config() -> WorkerConfig:
    config = WorkerConfig(
        worker_id=os.getenv("ANALYSIS_WORKER_ID", "").strip()
        or f"{socket.gethostname()}-{uuid4().hex[:12]}",
        poll_seconds=float(os.getenv("ANALYSIS_WORKER_POLL_SECONDS", "1")),
        lease_seconds=float(os.getenv("ANALYSIS_JOB_LEASE_SECONDS", "120")),
        heartbeat_seconds=float(os.getenv("ANALYSIS_JOB_HEARTBEAT_SECONDS", "30")),
        max_attempts=int(os.getenv("ANALYSIS_JOB_MAX_ATTEMPTS", "3")),
    )
    config.validate()
    return config


def _heartbeat_loop(
    *,
    stop_event: threading.Event,
    job_id: str,
    config: WorkerConfig,
) -> None:
    while not stop_event.wait(config.heartbeat_seconds):
        with SessionLocal() as db:
            if not renew_job_lease(
                db,
                job_id=job_id,
                worker_id=config.worker_id,
                lease_seconds=config.lease_seconds,
            ):
                return


def process_job(job_id: str, config: WorkerConfig) -> str:
    attempts = 0
    heartbeat_stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat_loop,
        kwargs={
            "stop_event": heartbeat_stop,
            "job_id": job_id,
            "config": config,
        },
        daemon=True,
    )
    heartbeat.start()
    started = time.perf_counter()
    try:
        with SessionLocal() as db:
            job = db.scalar(
                select(AnalysisJob)
                .options(
                    selectinload(AnalysisJob.document).selectinload(
                        Document.clauses
                    )
                )
                .where(AnalysisJob.id == job_id)
            )
            if (
                job is None
                or job.status != "running"
                or job.worker_id != config.worker_id
            ):
                log_event(
                    logger=logger,
                    event="analysis_job_claim_lost",
                    service="worker",
                    status="failed",
                    worker_id=config.worker_id,
                    job_id=job_id,
                    event_category="operational",
                    outcome="failed",
                    safe_error_code="ANALYSIS_CLAIM_LOST",
                )
                return "claim_lost"
            db.execute(
                delete(AnalysisResultItem).where(
                    AnalysisResultItem.analysis_job_id == job.id
                )
            )
            try:
                attempts = job.attempt_count
                run_analysis_pipeline(
                    db=db,
                    job=job,
                    clauses=sorted(job.document.clauses, key=lambda item: item.ordinal),
                    provider=create_analysis_provider(),
                    worker_managed=True,
                )
                finish_job_success(db, job=job, worker_id=config.worker_id)
                outcome = "completed"
            except Exception as exc:
                db.rollback()
                outcome = finish_job_failure(
                    db,
                    job_id=job_id,
                    worker_id=config.worker_id,
                    error=exc,
                )
                failed_job = db.get(AnalysisJob, job_id)
                safe_error_code = (
                    failed_job.last_error_code
                    if failed_job is not None
                    else "analysis_claim_lost"
                )
                log_event(
                    logger=logger,
                    event=(
                        "analysis_job_retry_scheduled"
                        if outcome == "pending"
                        else (
                            "analysis_job_claim_lost"
                            if outcome == "claim_lost"
                            else "analysis_job_failed_terminal"
                        )
                    ),
                    service="worker",
                    status=outcome,
                    worker_id=config.worker_id,
                    job_id=job_id,
                    attempt_count=attempts,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    safe_error_code=safe_error_code,
                    event_category="operational",
                    outcome="scheduled" if outcome == "pending" else "failed",
                    alert_candidate=outcome == "failed",
                )
                return outcome

        log_event(
            logger=logger,
            event="analysis_job_completed",
            service="worker",
            status=outcome,
            worker_id=config.worker_id,
            job_id=job_id,
            attempt_count=attempts,
            duration_ms=int((time.perf_counter() - started) * 1000),
            event_category="operational",
            outcome="success",
        )
        return outcome
    finally:
        heartbeat_stop.set()
        heartbeat.join(timeout=config.heartbeat_seconds + 1)


def run_worker(
    *,
    config: WorkerConfig | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    worker_config = config or load_worker_config()
    worker_config.validate()
    shutdown = stop_event or threading.Event()
    logger = logging.getLogger("worker")
    log_event(
        logger=logger,
        event="analysis_worker_started",
        service="worker",
        status="started",
        worker_id=worker_config.worker_id,
    )
    while not shutdown.is_set():
        with SessionLocal() as db:
            recovery = recover_stale_jobs_result(db)
            if recovery.retried_count:
                log_event(
                    logger=logger,
                    event="analysis_job_stale_recovered",
                    service="worker",
                    status="scheduled",
                    worker_id=worker_config.worker_id,
                    attempt_count=recovery.retried_count,
                    outcome="scheduled",
                    alert_candidate=recovery.retried_count > 1,
                )
            if recovery.failed_count:
                log_event(
                    logger=logger,
                    event="analysis_job_stale_failed",
                    service="worker",
                    status="failed",
                    worker_id=worker_config.worker_id,
                    attempt_count=recovery.failed_count,
                    outcome="failed",
                    safe_error_code="MAX_ATTEMPTS_EXCEEDED",
                    alert_candidate=True,
                )
            job = claim_next_job(
                db,
                worker_id=worker_config.worker_id,
                lease_seconds=worker_config.lease_seconds,
                max_attempts=worker_config.max_attempts,
            )
        if job is None:
            shutdown.wait(worker_config.poll_seconds)
            continue
        process_job(job.id, worker_config)
    log_event(
        logger=logger,
        event="analysis_worker_stopped",
        service="worker",
        status="stopped",
        worker_id=worker_config.worker_id,
    )


def main() -> None:
    configure_logging("worker")
    stop_event = threading.Event()

    def request_shutdown(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    run_worker(stop_event=stop_event)


if __name__ == "__main__":
    main()
