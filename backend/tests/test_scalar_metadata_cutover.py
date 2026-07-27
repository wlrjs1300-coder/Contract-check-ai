from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect, text

from backend.tests.test_migrations import (
    _engine,
    _load_alembic_config,
    _reset_sqlite_db,
)


def test_0005_upgrade_from_0004_empty_db(tmp_path: Path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'cutover.sqlite'}"
    _reset_sqlite_db(db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = _load_alembic_config(db_url)
    command.upgrade(config, "0004_scalar_metadata_additive")
    command.upgrade(config, "0005_scalar_metadata_cutover")
    engine = _engine(db_url)
    try:
        inspector = inspect(engine)
        assert "email" not in {
            column["name"] for column in inspector.get_columns("users")
        }
        assert "filename" not in {
            column["name"] for column in inspector.get_columns("documents")
        }
        assert "filename_display" not in {
            column["name"] for column in inspector.get_columns("extractions")
        }
        assert "title" not in {
            column["name"] for column in inspector.get_columns("clauses")
        }
        indexes = {
            index["name"]: index for index in inspector.get_indexes("users")
        }
        assert indexes["ix_users_email_lookup_hash"]["unique"]
    finally:
        engine.dispose()


def test_0005_upgrade_rejects_null_required_columns(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite:///{tmp_path / 'cutover-null.sqlite'}"
    _reset_sqlite_db(db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = _load_alembic_config(db_url)
    command.upgrade(config, "0004_scalar_metadata_additive")
    engine = _engine(db_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id, email, password_hash, is_active, auth_version,
                        created_at, updated_at
                    ) VALUES (
                        '00000000-0000-4000-8000-000000000001',
                        'legacy@example.invalid', 'hash', 1, 1,
                        '2026-01-01', '2026-01-01'
                    )
                    """
                )
            )
    finally:
        engine.dispose()
    with pytest.raises(RuntimeError):
        command.upgrade(config, "0005_scalar_metadata_cutover")


def test_0005_downgrade_blocks_populated_encrypted_db(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite:///{tmp_path / 'cutover-down.sqlite'}"
    _reset_sqlite_db(db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = _load_alembic_config(db_url)
    command.upgrade(config, "0005_scalar_metadata_cutover")
    engine = _engine(db_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id, email_encrypted, email_lookup_hash, password_hash,
                        is_active, auth_version, created_at, updated_at
                    ) VALUES (
                        '00000000-0000-4000-8000-000000000001',
                        'synthetic-envelope',
                        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                        'hash', 1, 1, '2026-01-01', '2026-01-01'
                    )
                    """
                )
            )
    finally:
        engine.dispose()
    with pytest.raises(RuntimeError):
        command.downgrade(config, "0004_scalar_metadata_additive")


def test_0005_source_reads_no_secret_and_performs_no_backfill() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0005_scalar_metadata_cutover.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "os.getenv",
        "EMAIL_LOOKUP_HMAC_KEY",
        "DATA_ENCRYPTION_KEYS_JSON",
        "UPDATE ",
        "INSERT ",
    ):
        assert forbidden not in source
