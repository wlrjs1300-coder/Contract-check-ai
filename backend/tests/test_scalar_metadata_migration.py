from pathlib import Path

from alembic import command
from sqlalchemy import inspect, text

from backend.tests.test_migrations import (
    _engine,
    _load_alembic_config,
    _reset_sqlite_db,
)


def test_migration_0004_preserves_populated_legacy_user(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_url = f"sqlite:///{tmp_path / 'scalar_metadata.sqlite'}"
    _reset_sqlite_db(db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = _load_alembic_config(db_url)
    command.upgrade(config, "0003_scalar_field_encryption")

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
                        :id, :email, :password_hash, 1, 1,
                        :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": "00000000-0000-4000-8000-000000000001",
                    "email": "legacy@example.invalid",
                    "password_hash": "synthetic-hash",
                    "created_at": "2026-01-01 00:00:00",
                    "updated_at": "2026-01-01 00:00:00",
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "0004_scalar_metadata_additive")
    engine = _engine(db_url)
    try:
        columns = {item["name"]: item for item in inspect(engine).get_columns("users")}
        assert columns["email_encrypted"]["nullable"] is True
        assert columns["email_lookup_hash"]["nullable"] is True
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT email, email_encrypted, email_lookup_hash "
                    "FROM users"
                )
            ).one()
        assert row == ("legacy@example.invalid", None, None)
    finally:
        engine.dispose()

    command.downgrade(config, "0003_scalar_field_encryption")
    engine = _engine(db_url)
    try:
        columns = {item["name"] for item in inspect(engine).get_columns("users")}
        assert "email" in columns
        assert "email_encrypted" not in columns
        assert "email_lookup_hash" not in columns
    finally:
        engine.dispose()


def test_migration_0004_source_has_no_runtime_secret_or_backfill() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0004_scalar_metadata_additive.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "os.getenv",
        "EMAIL_LOOKUP_HMAC_KEY",
        "DATA_ENCRYPTION_KEYS_JSON",
        "UPDATE ",
        "INSERT ",
    ):
        assert forbidden not in source
