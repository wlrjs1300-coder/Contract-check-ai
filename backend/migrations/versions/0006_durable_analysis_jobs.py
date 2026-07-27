"""Add durable execution metadata to analysis jobs."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from alembic import op
import sqlalchemy as sa


revision = "0006_durable_analysis_jobs"
down_revision = "0005_scalar_metadata_cutover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = datetime.utcnow()
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3")
        )
        batch_op.add_column(
            sa.Column("available_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("finished_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("worker_id", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("last_error_code", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_error_message_safe", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("request_fingerprint", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("active_dedupe_key", sa.String(length=64), nullable=True)
        )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, status, created_at FROM analysis_jobs")
    ).mappings().all()
    for row in rows:
        fingerprint = sha256(
            f"legacy-analysis-job:{row['id']}".encode("ascii")
        ).hexdigest()
        status = row["status"]
        normalized = "pending" if status in {"queued", "processing", "running"} else status
        active_key = fingerprint if normalized == "pending" else None
        finished_at = now if normalized in {"completed", "failed"} else None
        connection.execute(
            sa.text(
                """
                UPDATE analysis_jobs
                SET status = :status,
                    available_at = COALESCE(created_at, :now),
                    finished_at = :finished_at,
                    request_fingerprint = :fingerprint,
                    active_dedupe_key = :active_key
                WHERE id = :job_id
                """
            ),
            {
                "status": normalized,
                "now": now,
                "finished_at": finished_at,
                "fingerprint": fingerprint,
                "active_key": active_key,
                "job_id": row["id"],
            },
        )

    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.alter_column(
            "attempt_count",
            existing_type=sa.Integer(),
            server_default=None,
        )
        batch_op.alter_column(
            "max_attempts",
            existing_type=sa.Integer(),
            server_default=None,
        )
        batch_op.alter_column(
            "available_at",
            existing_type=sa.DateTime(),
            nullable=False,
        )
        batch_op.alter_column(
            "request_fingerprint",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_index(
            "ix_analysis_jobs_status_available_at",
            ["status", "available_at"],
        )
        batch_op.create_index(
            "ix_analysis_jobs_status_lease_expires_at",
            ["status", "lease_expires_at"],
        )
        batch_op.create_unique_constraint(
            "uq_analysis_jobs_active_dedupe_key",
            ["active_dedupe_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.drop_constraint(
            "uq_analysis_jobs_active_dedupe_key",
            type_="unique",
        )
        batch_op.drop_index("ix_analysis_jobs_status_lease_expires_at")
        batch_op.drop_index("ix_analysis_jobs_status_available_at")
        batch_op.drop_column("active_dedupe_key")
        batch_op.drop_column("request_fingerprint")
        batch_op.drop_column("last_error_message_safe")
        batch_op.drop_column("last_error_code")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("finished_at")
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("available_at")
        batch_op.drop_column("max_attempts")
        batch_op.drop_column("attempt_count")
