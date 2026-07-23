from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    JSON,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy import Column, Index, Table
from sqlalchemy.engine import Engine
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
from backend.app.db import models  # noqa: F401


def _reset_sqlite_db(database_url: str) -> None:
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        db_path = Path(database_url[len(prefix) :])
        db_path.unlink(missing_ok=True)


def _load_alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _engine(database_url: str) -> Engine:
    eng = create_engine(database_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(eng, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    return eng


def _revision(database_url: str) -> str | None:
    eng = create_engine(database_url)
    try:
        with eng.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    finally:
        eng.dispose()


def _expected_no_default_columns() -> set[tuple[str, str]]:
    return {
        ("documents", "unclassified_sections"),
        ("documents", "document_warnings"),
        ("clauses", "warnings"),
        ("analysis_result_items", "expert_review_recommended"),
        ("analysis_result_items", "extra_data"),
        ("extractions", "warnings"),
        ("extractions", "requires_user_review"),
        ("extractions", "extra_data"),
        ("extraction_pages", "warnings"),
        ("extraction_pages", "requires_user_review"),
        ("extraction_pages", "extra_data"),
    }


def _assert_defaults_are_none(database_url: str) -> None:
    eng = _engine(database_url)
    try:
        insp = inspect(eng)
        for table_name, column_name in _expected_no_default_columns():
            cols = {c["name"]: c for c in insp.get_columns(table_name)}
            assert cols[column_name]["default"] is None
    finally:
        eng.dispose()


def _assert_fk_match(expected_table: Table, actual_fks: list[dict], table_name: str) -> None:
    for fk in expected_table.foreign_key_constraints:
        expected = (
            tuple(fk.column_keys),
            fk.elements[0].column.table.name,
            tuple(el.column.name for el in fk.elements),
            fk.ondelete,
        )

        for actual in actual_fks:
            actual_tuple = (
                tuple(actual["constrained_columns"]),
                actual["referred_table"],
                tuple(actual["referred_columns"]),
                (actual["options"] or {}).get("ondelete"),
            )
            if expected == actual_tuple:
                break
        else:
            raise AssertionError(f"Missing FK expectation on {table_name}: {expected}")


def _normalize_sqlite_type(type_value: object) -> str:
    rendered = str(type_value)
    token = rendered.split("(", 1)[0].strip().upper()
    if token in {"VARCHAR", "NVARCHAR", "CHAR", "NCHAR", "STRING"}:
        return "STRING"
    if token in {"INT", "INTEGER", "BIGINT", "SMALLINT"}:
        return "INTEGER"
    if token in {"DATETIME", "TIMESTAMP"}:
        return "DATETIME"
    if token in {"BOOL", "BOOLEAN"}:
        return "BOOLEAN"
    if token in {"JSON", "JSONB"}:
        return "JSON"
    if token in {"TEXT", "VARCHAR", "NVARCHAR", "CHAR", "NCHAR", "STRING"}:
        return "STRING"
    return token


def _assert_metadata_parity(expected: MetaData, url: str) -> None:
    eng = _engine(url)
    try:
        insp = inspect(eng)
        expected_table_names = set(expected.tables.keys())
        actual_table_names = set(insp.get_table_names()) - {"alembic_version"}
        assert actual_table_names == expected_table_names

        for table_name in expected_table_names:
            table = expected.tables[table_name]
            actual_columns = {c["name"]: c for c in insp.get_columns(table_name)}
            expected_columns = {c.name: c for c in table.columns if c.name}
            assert set(actual_columns.keys()) == set(expected_columns.keys())

            for expected_column in expected_columns.values():
                if not expected_column.name:
                    continue
                actual = actual_columns[expected_column.name]
                assert bool(actual["nullable"]) == bool(expected_column.nullable)
                assert bool(actual["primary_key"]) == bool(expected_column.primary_key)
                expected_type = _normalize_sqlite_type(
                    expected_column.type.compile(dialect=sqlite_dialect.dialect())
                )
                actual_type = _normalize_sqlite_type(actual["type"])
                assert actual_type == expected_type, (
                    f"Type mismatch for {table_name}.{expected_column.name}: "
                    f"expected {expected_type}, actual {actual_type}"
                )

            actual_indexes = {
                (idx["name"], tuple(idx["column_names"]), bool(idx["unique"]))
                for idx in insp.get_indexes(table_name)
            }
            expected_indexes = {
                (idx.name, tuple(col.name for col in idx.columns), bool(idx.unique))
                for idx in table.indexes
            }
            assert expected_indexes.issubset(actual_indexes)

            expected_uqs = {
                (uq.name, tuple(col.name for col in uq.columns))
                for uq in table.constraints
                if isinstance(uq, UniqueConstraint)
            }
            actual_uqs = {
                (uq["name"], tuple(uq["column_names"])) for uq in insp.get_unique_constraints(table_name)
            }
            assert expected_uqs.issubset(actual_uqs)

            _assert_fk_match(table, insp.get_foreign_keys(table_name), table_name)
    finally:
        eng.dispose()


def _expected_v0733_schema() -> MetaData:
    metadata = MetaData()

    Table(
        "documents",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("filename", String(255), nullable=False),
        Column("content_type", String(100), nullable=True),
        Column("size_bytes", Integer, nullable=False),
        Column("character_count", Integer, nullable=False),
        Column("status", String(50), nullable=False),
        Column("unclassified_sections", JSON, nullable=False),
        Column("document_warnings", JSON, nullable=False),
        Column("created_at", DateTime, nullable=False),
    )

    clauses = Table(
        "clauses",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("clause_id", String(50), nullable=False),
        Column("document_id", String(36), nullable=False),
        Column("reference_id", String(100), nullable=False),
        Column("source_hash", String(64), nullable=False),
        Column("ordinal", Integer, nullable=False),
        Column("marker", String(50), nullable=False),
        Column("clause_type", String(50), nullable=False),
        Column("title", String(255), nullable=True),
        Column("body", Text, nullable=False),
        Column("warnings", JSON, nullable=False),
        ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        UniqueConstraint("document_id", "clause_id", name="uq_clauses_document_clause"),
    )
    Index("ix_clauses_document_id", clauses.c.document_id)
    Index("ix_clauses_reference_id", clauses.c.reference_id, unique=True)

    analysis_jobs = Table(
        "analysis_jobs",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("document_id", String(36), nullable=False),
        Column("status", String(50), nullable=False),
        Column("created_at", DateTime, nullable=False),
        ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    Index("ix_analysis_jobs_document_id", analysis_jobs.c.document_id)

    analysis_result_items = Table(
        "analysis_result_items",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("analysis_job_id", String(36), nullable=False),
        Column("clause_record_id", String(36), nullable=False),
        Column("reference_id", String(100), nullable=False),
        Column("display_label", String(50), nullable=False),
        Column("summary", Text, nullable=False),
        Column("expert_review_recommended", Boolean, nullable=False),
        Column("extra_data", JSON, nullable=False),
        ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["clause_record_id"], ["clauses.id"], ondelete="CASCADE"),
    )
    Index("ix_analysis_result_items_analysis_job_id", analysis_result_items.c.analysis_job_id)
    Index("ix_analysis_result_items_clause_record_id", analysis_result_items.c.clause_record_id)
    Index("ix_analysis_result_items_reference_id", analysis_result_items.c.reference_id)

    Table(
        "extractions",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("filename_display", String(255), nullable=False),
        Column("source_type", String(20), nullable=False),
        Column("size_bytes", Integer, nullable=False),
        Column("page_count", Integer, nullable=False),
        Column("status", String(50), nullable=False),
        Column("method", String(20), nullable=False),
        Column("warnings", JSON, nullable=False),
        Column("requires_user_review", Boolean, nullable=False),
        Column("extra_data", JSON, nullable=False),
        Column("created_at", DateTime, nullable=False),
    )

    extraction_pages = Table(
        "extraction_pages",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("extraction_id", String(36), nullable=False),
        Column("page_number", Integer, nullable=False),
        Column("method", String(20), nullable=False),
        Column("text", Text, nullable=False),
        Column("warnings", JSON, nullable=False),
        Column("requires_user_review", Boolean, nullable=False),
        Column("extra_data", JSON, nullable=False),
        ForeignKeyConstraint(["extraction_id"], ["extractions.id"], ondelete="CASCADE"),
        UniqueConstraint("extraction_id", "page_number", name="uq_extraction_pages_number"),
    )
    Index("ix_extraction_pages_extraction_id", extraction_pages.c.extraction_id)

    return metadata


def _insert_legacy_document(database_url: str) -> None:
    eng = create_engine(database_url)
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO documents (
                        id, filename, content_type, size_bytes, character_count, status,
                        unclassified_sections, document_warnings, created_at
                    ) VALUES (
                        :id, :filename, :content_type, :size_bytes, :character_count, :status,
                        :unclassified_sections, :document_warnings, :created_at
                    )
                    """
                ),
                {
                    "id": "00000000-0000-4000-8000-000000000001",
                    "filename": "legacy.txt",
                    "content_type": "text/plain",
                    "size_bytes": 1,
                    "character_count": 1,
                    "status": "uploaded",
                    "unclassified_sections": "[]",
                    "document_warnings": "[]",
                    "created_at": "2026-01-01 00:00:00",
                },
            )
    finally:
        eng.dispose()


def _insert_legacy_extraction(database_url: str) -> None:
    eng = create_engine(database_url)
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO extractions (
                        id, filename_display, source_type, size_bytes, page_count, status, method,
                        warnings, requires_user_review, extra_data, created_at
                    ) VALUES (
                        :id, :filename_display, :source_type, :size_bytes, :page_count, :status, :method,
                        :warnings, :requires_user_review, :extra_data, :created_at
                    )
                    """
                ),
                {
                    "id": "00000000-0000-4000-8000-000000000002",
                    "filename_display": "legacy.pdf",
                    "source_type": "pdf",
                    "size_bytes": 1,
                    "page_count": 1,
                    "status": "uploaded",
                    "method": "direct",
                    "warnings": "[]",
                    "requires_user_review": 0,
                    "extra_data": "{}",
                    "created_at": "2026-01-01 00:00:00",
                },
            )
    finally:
        eng.dispose()


def _row_count(database_url: str, table_name: str) -> int:
    eng = create_engine(database_url)
    try:
        with eng.connect() as conn:
            return conn.execute(text(f"SELECT COUNT(*) AS cnt FROM {table_name}")).scalar_one()
    finally:
        eng.dispose()


def _assert_no_users_and_owner_columns(database_url: str) -> None:
    eng = _engine(database_url)
    try:
        insp = inspect(eng)
        assert not insp.has_table("users")
        document_cols = {c["name"] for c in insp.get_columns("documents")}
        extraction_cols = {c["name"] for c in insp.get_columns("extractions")}
        assert "owner_id" not in document_cols
        assert "owner_id" not in extraction_cols
    finally:
        eng.dispose()


def test_sqlite_foreign_keys_enabled() -> None:
    eng = _engine("sqlite://")
    try:
        with eng.connect() as conn:
            assert int(conn.execute(text("PRAGMA foreign_keys")).scalar_one()) == 1
    finally:
        eng.dispose()


def test_migration_0001_parity_with_expected_v0733_schema(tmp_path: Path, monkeypatch) -> None:
    expected_url = f"sqlite:///{tmp_path / 'expected_v0733.sqlite'}"
    migrated_url = f"sqlite:///{tmp_path / 'migrated_0001.sqlite'}"

    _reset_sqlite_db(expected_url)
    _reset_sqlite_db(migrated_url)
    monkeypatch.setenv("DATABASE_URL", migrated_url)

    expected = _expected_v0733_schema()
    expected_engine = _engine(expected_url)
    try:
        expected.create_all(bind=expected_engine)
    finally:
        expected_engine.dispose()

    config = _load_alembic_config(migrated_url)
    command.upgrade(config, "0001_current_schema_baseline")
    try:
        _assert_metadata_parity(expected, migrated_url)
        _assert_defaults_are_none(migrated_url)

        inspect_eng = _engine(migrated_url)
        try:
            insp = inspect(inspect_eng)
            assert any(
                idx["name"] == "ix_clauses_reference_id" and idx["unique"]
                for idx in insp.get_indexes("clauses")
            )
            assert not any(
                idx["name"] == "ix_extraction_pages_page_number"
                for idx in insp.get_indexes("extraction_pages")
            )
        finally:
            inspect_eng.dispose()
    finally:
        command.downgrade(config, "base")


def test_migration_0002_blocks_legacy_document_rows(tmp_path: Path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'legacy_document_rows.sqlite'}"
    _reset_sqlite_db(db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = _load_alembic_config(db_url)

    try:
        command.upgrade(config, "0001_current_schema_baseline")
        _insert_legacy_document(db_url)

        with pytest.raises(RuntimeError, match="Legacy development data must be cleared before ownership migration."):
            command.upgrade(config, "0002_auth_ownership")

        assert _revision(db_url) == "0001_current_schema_baseline"
        _assert_no_users_and_owner_columns(db_url)
        assert _row_count(db_url, "documents") == 1
        assert _row_count(db_url, "extractions") == 0
    finally:
        command.downgrade(config, "base")


def test_migration_0002_blocks_legacy_extraction_rows(tmp_path: Path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'legacy_extraction_rows.sqlite'}"
    _reset_sqlite_db(db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = _load_alembic_config(db_url)

    try:
        command.upgrade(config, "0001_current_schema_baseline")
        _insert_legacy_extraction(db_url)

        with pytest.raises(RuntimeError, match="Legacy development data must be cleared before ownership migration."):
            command.upgrade(config, "0002_auth_ownership")

        assert _revision(db_url) == "0001_current_schema_baseline"
        _assert_no_users_and_owner_columns(db_url)
        assert _row_count(db_url, "extractions") == 1
        assert _row_count(db_url, "documents") == 0
    finally:
        command.downgrade(config, "base")


def test_migration_head_matches_orm_metadata(tmp_path: Path, monkeypatch) -> None:
    orm_url = f"sqlite:///{tmp_path / 'orm.sqlite'}"
    head_url = f"sqlite:///{tmp_path / 'head.sqlite'}"
    _reset_sqlite_db(orm_url)
    _reset_sqlite_db(head_url)

    orm_engine = _engine(orm_url)
    try:
        Base.metadata.create_all(bind=orm_engine)
    finally:
        orm_engine.dispose()

    config = _load_alembic_config(head_url)
    monkeypatch.setenv("DATABASE_URL", head_url)
    command.upgrade(config, "head")
    try:
        expected = Base.metadata
        _assert_metadata_parity(expected, head_url)

        head_engine = _engine(head_url)
        try:
            insp = inspect(head_engine)
            assert any(c["name"] == "ck_users_auth_version_positive" for c in insp.get_check_constraints("users"))

            user_cols = {c["name"]: c for c in insp.get_columns("users")}
            for col in ["is_active", "auth_version", "created_at", "updated_at"]:
                assert user_cols[col]["default"] is None

            user_indexes = {i["name"]: i for i in insp.get_indexes("users")}
            assert bool(user_indexes["ix_users_email"]["unique"]) is True

            for table_name in ("documents", "extractions"):
                cols = {c["name"] for c in insp.get_columns(table_name)}
                assert "owner_id" in cols
                fk_rows = [
                    fk for fk in insp.get_foreign_keys(table_name) if fk["constrained_columns"] == ["owner_id"]
                ]
                assert len(fk_rows) == 1
                assert fk_rows[0]["referred_table"] == "users"
                assert (fk_rows[0].get("options") or {}).get("ondelete") == "RESTRICT"

                index_names = {i["name"] for i in insp.get_indexes(table_name)}
                assert f"ix_{table_name}_owner_id" in index_names

            assert "owner_id" not in {c["name"] for c in insp.get_columns("analysis_jobs")}
        finally:
            head_engine.dispose()
    finally:
        command.downgrade(config, "base")


def test_migration_upgrade_and_downgrade_roundtrip(tmp_path: Path, monkeypatch) -> None:
    db_url = f"sqlite:///{tmp_path / 'upgrade_down_roundtrip.sqlite'}"
    _reset_sqlite_db(db_url)
    monkeypatch.setenv("DATABASE_URL", db_url)
    config = _load_alembic_config(db_url)

    command.upgrade(config, "head")
    try:
        eng = _engine(db_url)
        try:
            insp = inspect(eng)
            assert insp.has_table("users")
            assert insp.has_table("documents")
            assert insp.has_table("extractions")
            assert "ix_documents_owner_id" in {i["name"] for i in insp.get_indexes("documents")}
            assert "ix_extractions_owner_id" in {i["name"] for i in insp.get_indexes("extractions")}
            assert "owner_id" in {c["name"] for c in insp.get_columns("documents")}
            assert "owner_id" in {c["name"] for c in insp.get_columns("extractions")}
            assert "owner_id" not in {c["name"] for c in insp.get_columns("analysis_jobs")}
        finally:
            eng.dispose()

        command.downgrade(config, "base")

        eng2 = _engine(db_url)
        try:
            insp2 = inspect(eng2)
            assert not insp2.has_table("users")
            assert not insp2.has_table("documents")
            assert not insp2.has_table("extractions")
        finally:
            eng2.dispose()
    finally:
        command.downgrade(config, "base")
