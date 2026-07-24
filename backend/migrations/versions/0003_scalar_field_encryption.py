"""Replace plaintext scalar columns with encrypted-only columns."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_scalar_field_encryption"
down_revision = "0002_auth_ownership"
branch_labels = None
depends_on = None


_UPGRADE_BLOCKED_MESSAGE = (
    "Existing development data must be cleared before scalar encryption migration."
)
_DOWNGRADE_BLOCKED_MESSAGE = (
    "Encrypted development data must be cleared before scalar encryption downgrade."
)
_UNEXPECTED_SCHEMA_MESSAGE = "Unexpected schema for scalar field encryption migration."

_TABLES = ("clauses", "extraction_pages", "analysis_result_items")
_PLAINTEXT_COLUMN = {
    "clauses": "body",
    "extraction_pages": "text",
    "analysis_result_items": "summary",
}
_ENCRYPTED_COLUMN = {
    "clauses": "body_encrypted",
    "extraction_pages": "text_encrypted",
    "analysis_result_items": "summary_encrypted",
}
_UNIQUE_CONSTRAINT_NAME = "uq_analysis_result_items_job_clause"
_UNIQUE_CONSTRAINT_COLUMNS = ["analysis_job_id", "clause_record_id"]


def _table_has_rows(connection: sa.engine.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")
        ).scalar_one_or_none()
        is not None
    )


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _has_constraint(inspector: sa.Inspector, table_name: str, name: str) -> bool:
    return any(
        constraint["name"] == name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _assert_pre_upgrade_schema(inspector: sa.Inspector) -> None:
    for table_name in _TABLES:
        if not inspector.has_table(table_name):
            raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)

        columns = _column_names(inspector, table_name)
        if _PLAINTEXT_COLUMN[table_name] not in columns:
            raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)
        if _ENCRYPTED_COLUMN[table_name] in columns:
            raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)

    if _has_constraint(inspector, "analysis_result_items", _UNIQUE_CONSTRAINT_NAME):
        raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)


def _assert_pre_downgrade_schema(inspector: sa.Inspector) -> None:
    for table_name in _TABLES:
        if not inspector.has_table(table_name):
            raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)

        columns = _column_names(inspector, table_name)
        if _ENCRYPTED_COLUMN[table_name] not in columns:
            raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)
        if _PLAINTEXT_COLUMN[table_name] in columns:
            raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)

    if not _has_constraint(inspector, "analysis_result_items", _UNIQUE_CONSTRAINT_NAME):
        raise RuntimeError(_UNEXPECTED_SCHEMA_MESSAGE)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    _assert_pre_upgrade_schema(inspector)

    for table_name in _TABLES:
        if _table_has_rows(connection, table_name):
            raise RuntimeError(_UPGRADE_BLOCKED_MESSAGE)

    with op.batch_alter_table("clauses") as batch_op:
        batch_op.add_column(sa.Column("body_encrypted", sa.Text(), nullable=False))
        batch_op.drop_column("body")

    with op.batch_alter_table("extraction_pages") as batch_op:
        batch_op.add_column(sa.Column("text_encrypted", sa.Text(), nullable=False))
        batch_op.drop_column("text")

    with op.batch_alter_table("analysis_result_items") as batch_op:
        batch_op.add_column(sa.Column("summary_encrypted", sa.Text(), nullable=False))
        batch_op.drop_column("summary")
        batch_op.create_unique_constraint(
            _UNIQUE_CONSTRAINT_NAME,
            _UNIQUE_CONSTRAINT_COLUMNS,
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    _assert_pre_downgrade_schema(inspector)

    for table_name in _TABLES:
        if _table_has_rows(connection, table_name):
            raise RuntimeError(_DOWNGRADE_BLOCKED_MESSAGE)

    with op.batch_alter_table("analysis_result_items") as batch_op:
        batch_op.drop_constraint(_UNIQUE_CONSTRAINT_NAME, type_="unique")
        batch_op.add_column(sa.Column("summary", sa.Text(), nullable=False))
        batch_op.drop_column("summary_encrypted")

    with op.batch_alter_table("extraction_pages") as batch_op:
        batch_op.add_column(sa.Column("text", sa.Text(), nullable=False))
        batch_op.drop_column("text_encrypted")

    with op.batch_alter_table("clauses") as batch_op:
        batch_op.add_column(sa.Column("body", sa.Text(), nullable=False))
        batch_op.drop_column("body_encrypted")
