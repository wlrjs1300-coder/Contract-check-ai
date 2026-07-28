from __future__ import annotations

import os
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


class ReadinessError(RuntimeError):
    """Raised when service readiness checks fail."""

    def __init__(self, code: str) -> None:
        super().__init__("Service is not ready.")
        self.code = code


_ALembicIniPath = Path(__file__).resolve().parents[2] / "alembic.ini"


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./contract_check.db")


def _build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def _assert_database_connectivity(database_url: str) -> None:
    try:
        engine = _build_engine(database_url)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except SQLAlchemyError as exc:
        raise ReadinessError("database_unreachable") from exc


def _current_alembic_head() -> str:
    config = Config(str(_ALembicIniPath))
    config.set_main_option("sqlalchemy.url", _database_url())
    config.set_main_option("script_location", str(_ALembicIniPath.parent / "migrations"))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head() or ""


def _assert_alembic_head(database_url: str) -> None:
    try:
        expected_head = _current_alembic_head()
    except Exception as exc:  # pragma: no cover - config parsing is environment specific
        raise ReadinessError("alembic_head_unknown") from exc
    if not expected_head:
        raise ReadinessError("alembic_head_unknown")

    try:
        engine = _build_engine(database_url)
        try:
            with engine.connect() as connection:
                version_num = connection.execute(
                    text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
                ).scalar_one_or_none()
        finally:
            engine.dispose()
    except SQLAlchemyError as exc:
        raise ReadinessError("migration_table_missing") from exc

    if version_num is None:
        raise ReadinessError("migration_version_missing")

    if str(version_num) != expected_head:
        raise ReadinessError("migration_head_mismatch")


def get_readiness_status(database_url: str | None = None) -> dict[str, str]:
    target_url = database_url or _database_url()
    if not target_url:
        raise ReadinessError("database_url_missing")

    _assert_database_connectivity(target_url)
    _assert_alembic_head(target_url)
    return {"status": "ready"}


def assert_service_ready(database_url: str | None = None) -> None:
    get_readiness_status(database_url=database_url)
