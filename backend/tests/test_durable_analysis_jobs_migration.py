from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config(database_url: str) -> Config:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_0006_upgrade_preserves_and_normalizes_existing_jobs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    url = f"sqlite:///{tmp_path / 'durable.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)
    command.upgrade(config, "0005_scalar_metadata_cutover")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users
                    (id, email_encrypted, email_lookup_hash, password_hash,
                     is_active, auth_version, created_at, updated_at)
                VALUES
                    ('owner', 'encrypted', :lookup, 'hash', 1, 1,
                     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"lookup": "a" * 64},
        )
        connection.execute(
            text(
                """
                INSERT INTO documents
                    (id, filename_encrypted, content_type, size_bytes,
                     character_count, status, unclassified_sections,
                     document_warnings, owner_id, created_at)
                VALUES
                    ('document', 'encrypted', 'text/plain', 1, 1, 'processed',
                     '[]', '[]', 'owner', CURRENT_TIMESTAMP)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO analysis_jobs (id, document_id, status, created_at)
                VALUES ('job', 'document', 'processing', CURRENT_TIMESTAMP)
                """
            )
        )
    command.upgrade(config, "0006_durable_analysis_jobs")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT * FROM analysis_jobs WHERE id = 'job'")
        ).mappings().one()
        assert row["status"] == "pending"
        assert row["available_at"] is not None
        assert len(row["request_fingerprint"]) == 64
        assert row["active_dedupe_key"] == row["request_fingerprint"]
    engine.dispose()


def test_0006_columns_indexes_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    url = f"sqlite:///{tmp_path / 'schema.sqlite'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("analysis_jobs")}
    assert {
        "attempt_count",
        "max_attempts",
        "available_at",
        "started_at",
        "heartbeat_at",
        "lease_expires_at",
        "finished_at",
        "worker_id",
        "last_error_code",
        "last_error_message_safe",
        "request_fingerprint",
        "active_dedupe_key",
    } <= columns
    indexes = {index["name"] for index in inspector.get_indexes("analysis_jobs")}
    assert "ix_analysis_jobs_status_available_at" in indexes
    assert "ix_analysis_jobs_status_lease_expires_at" in indexes
    engine.dispose()
    command.downgrade(config, "0005_scalar_metadata_cutover")
    engine = create_engine(url)
    columns = {
        column["name"] for column in inspect(engine).get_columns("analysis_jobs")
    }
    assert "request_fingerprint" not in columns
    engine.dispose()
