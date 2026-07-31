from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.db.models import AnalysisJob
from backend.app.services.provider_execution import ProviderExecutionError


SAFE_RETRY_MESSAGE = "Analysis is temporarily unavailable and will be retried."
SAFE_FAILED_MESSAGE = "Analysis could not be completed."
RETRY_DELAYS_SECONDS = (5.0, 30.0, 120.0)


@dataclass(frozen=True)
class StaleRecoveryResult:
    recovered_count: int
    retried_count: int
    failed_count: int


def claim_next_job(
    db: Session,
    *,
    worker_id: str,
    lease_seconds: float,
    max_attempts: int | None = None,
    now: datetime | None = None,
) -> AnalysisJob | None:
    claimed_at = now or datetime.utcnow()
    candidate_ids = db.scalars(
        select(AnalysisJob.id)
        .where(
            AnalysisJob.status == "pending",
            AnalysisJob.available_at <= claimed_at,
            AnalysisJob.attempt_count < AnalysisJob.max_attempts,
        )
        .order_by(AnalysisJob.available_at, AnalysisJob.created_at)
        .limit(20)
    ).all()
    for job_id in candidate_ids:
        result = db.execute(
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.status == "pending",
                AnalysisJob.available_at <= claimed_at,
                AnalysisJob.attempt_count < AnalysisJob.max_attempts,
            )
            .values(
                status="running",
                worker_id=worker_id,
                attempt_count=AnalysisJob.attempt_count + 1,
                max_attempts=(
                    max_attempts
                    if max_attempts is not None
                    else AnalysisJob.max_attempts
                ),
                started_at=func.coalesce(AnalysisJob.started_at, claimed_at),
                heartbeat_at=claimed_at,
                lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
                last_error_code=None,
                last_error_message_safe=None,
            )
        )
        if result.rowcount == 1:
            db.commit()
            return db.get(AnalysisJob, job_id)
        db.rollback()
    return None


def renew_job_lease(
    db: Session,
    *,
    job_id: str,
    worker_id: str,
    lease_seconds: float,
    now: datetime | None = None,
) -> bool:
    heartbeat_at = now or datetime.utcnow()
    result = db.execute(
        update(AnalysisJob)
        .where(
            AnalysisJob.id == job_id,
            AnalysisJob.status == "running",
            AnalysisJob.worker_id == worker_id,
        )
        .values(
            heartbeat_at=heartbeat_at,
            lease_expires_at=heartbeat_at + timedelta(seconds=lease_seconds),
        )
    )
    db.commit()
    return result.rowcount == 1


def recover_stale_jobs(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    return recover_stale_jobs_result(db, now=now).recovered_count


def recover_stale_jobs_result(
    db: Session,
    *,
    now: datetime | None = None,
) -> StaleRecoveryResult:
    recovered_at = now or datetime.utcnow()
    stale_ids = db.scalars(
        select(AnalysisJob.id).where(
            AnalysisJob.status == "running",
            AnalysisJob.lease_expires_at < recovered_at,
        )
    ).all()
    recovered = 0
    retried = 0
    failed = 0
    for job_id in stale_ids:
        job = db.get(AnalysisJob, job_id)
        if (
            job is None
            or job.status != "running"
            or job.lease_expires_at is None
            or job.lease_expires_at >= recovered_at
        ):
            continue
        expected_lease = job.lease_expires_at
        exhausted = job.attempt_count >= job.max_attempts
        values: dict[str, object] = {
            "worker_id": None,
            "heartbeat_at": None,
            "lease_expires_at": None,
        }
        if exhausted:
            values.update(
                status="failed",
                finished_at=recovered_at,
                active_dedupe_key=None,
                last_error_code="max_attempts_exceeded",
                last_error_message_safe=SAFE_FAILED_MESSAGE,
            )
        else:
            values.update(
                status="pending",
                available_at=recovered_at,
                last_error_code="worker_lease_expired",
                last_error_message_safe=SAFE_RETRY_MESSAGE,
            )
        result = db.execute(
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.status == "running",
                AnalysisJob.lease_expires_at == expected_lease,
            )
            .values(**values)
        )
        if result.rowcount == 1:
            recovered += 1
            if exhausted:
                failed += 1
            else:
                retried += 1
        db.commit()
    return StaleRecoveryResult(
        recovered_count=recovered,
        retried_count=retried,
        failed_count=failed,
    )


def retry_delay_seconds(
    attempt_count: int,
    *,
    jitter: Callable[[float, float], float] = random.uniform,
) -> float:
    index = min(max(attempt_count - 1, 0), len(RETRY_DELAYS_SECONDS) - 1)
    base = RETRY_DELAYS_SECONDS[index]
    return min(120.0, base + jitter(0.0, min(base * 0.2, 5.0)))


def finish_job_success(
    db: Session,
    *,
    job: AnalysisJob,
    worker_id: str,
    now: datetime | None = None,
) -> None:
    if job.status != "running" or job.worker_id != worker_id:
        db.rollback()
        raise RuntimeError("analysis_job_claim_lost")
    job.status = "completed"
    job.finished_at = now or datetime.utcnow()
    job.worker_id = None
    job.heartbeat_at = None
    job.lease_expires_at = None
    job.active_dedupe_key = None
    job.last_error_code = None
    job.last_error_message_safe = None
    db.commit()


def finish_job_failure(
    db: Session,
    *,
    job_id: str,
    worker_id: str,
    error: Exception,
    now: datetime | None = None,
    jitter: Callable[[float, float], float] = random.uniform,
) -> str:
    failed_at = now or datetime.utcnow()
    job = db.get(AnalysisJob, job_id)
    if job is None or job.status != "running" or job.worker_id != worker_id:
        db.rollback()
        return "claim_lost"

    retryable = isinstance(error, ProviderExecutionError) and error.retryable
    safe_code = (
        error.reason_code
        if isinstance(error, ProviderExecutionError)
        else "analysis_execution_failed"
    )
    job.worker_id = None
    job.heartbeat_at = None
    job.lease_expires_at = None
    job.last_error_code = safe_code
    if retryable and job.attempt_count < job.max_attempts:
        job.status = "pending"
        job.available_at = failed_at + timedelta(
            seconds=retry_delay_seconds(job.attempt_count, jitter=jitter)
        )
        job.last_error_message_safe = SAFE_RETRY_MESSAGE
        db.commit()
        return "pending"

    job.status = "failed"
    job.finished_at = failed_at
    job.active_dedupe_key = None
    job.last_error_message_safe = SAFE_FAILED_MESSAGE
    if retryable:
        job.last_error_code = "max_attempts_exceeded"
    db.commit()
    return "failed"
