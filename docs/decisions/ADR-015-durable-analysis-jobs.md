# ADR-015: Durable analysis jobs

## Status

Accepted for v0.8.0 PR-1.

## Decision

Analysis creation APIs enqueue a `pending` row and return immediately. A separate
DB polling worker claims work with a conditional update, executes the existing
encrypted analysis pipeline, and records a terminal state.

The queue uses the relational database already owned by the application. Redis,
RQ, and Celery are not part of the current architecture.

## Safety properties

- Only eligible `pending` jobs can be claimed.
- Claim increments the attempt and assigns a time-limited lease.
- A heartbeat extends only a lease owned by the same worker.
- Expired leases are requeued or failed after `max_attempts`.
- Retry stores only a safe error code and fixed message.
- Active SHA-256 dedupe keys prevent duplicate work.
- Fingerprints contain identifiers, revisions, source hashes, contract version,
  and provider identifier, never contract text, filenames, or email.
- Result rows and the `completed` transition share one transaction.
- Existing encryption envelope, AAD, hash, and stale policies are unchanged.

The worker command is:

```text
python -m backend.app.workers.analysis_worker
```

Readiness, Docker separation, migration one-shot deployment, structured JSON
logging, rate limiting, and upload hardening remain PR-2 scope.
