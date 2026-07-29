"""Cut over scalar metadata to encrypted-only columns."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_scalar_metadata_cutover"
down_revision = "0004_scalar_metadata_additive"
branch_labels = None
depends_on = None

_POPULATED_DOWNGRADE = (
    "Scalar metadata cutover downgrade requires an empty database."
)


def _scalar(connection: sa.engine.Connection, sql: str) -> int:
    return int(connection.execute(sa.text(sql)).scalar_one())


def upgrade() -> None:
    connection = op.get_bind()
    required = {
        "users": ("email_encrypted", "email_lookup_hash"),
        "documents": ("filename_encrypted",),
        "extractions": ("filename_display_encrypted",),
    }
    for table_name, columns in required.items():
        predicate = " OR ".join(f"{column} IS NULL" for column in columns)
        if _scalar(
            connection,
            f"SELECT COUNT(*) FROM {table_name} WHERE {predicate}",
        ):
            raise RuntimeError("Scalar metadata cutover precondition failed.")
    if _scalar(
        connection,
        """
        SELECT COUNT(*) FROM (
            SELECT email_lookup_hash
            FROM users
            GROUP BY email_lookup_hash
            HAVING COUNT(*) > 1
        ) AS duplicate_hashes
        """,
    ):
        raise RuntimeError("Scalar metadata cutover precondition failed.")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_email")
        batch_op.alter_column(
            "email_encrypted",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.alter_column(
            "email_lookup_hash",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_index(
            "ix_users_email_lookup_hash",
            ["email_lookup_hash"],
            unique=True,
        )
        batch_op.drop_column("email")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.alter_column(
            "filename_encrypted",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.drop_column("filename")
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.alter_column(
            "filename_display_encrypted",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.drop_column("filename_display")
    with op.batch_alter_table("clauses") as batch_op:
        batch_op.drop_column("title")


def downgrade() -> None:
    connection = op.get_bind()
    for table_name in ("users", "documents", "extractions", "clauses"):
        if _scalar(connection, f"SELECT COUNT(*) FROM {table_name}"):
            raise RuntimeError(_POPULATED_DOWNGRADE)

    with op.batch_alter_table("clauses") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.add_column(
            sa.Column("filename_display", sa.String(length=255), nullable=False)
        )
        batch_op.alter_column(
            "filename_display_encrypted",
            existing_type=sa.Text(),
            nullable=True,
        )
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column("filename", sa.String(length=255), nullable=False)
        )
        batch_op.alter_column(
            "filename_encrypted",
            existing_type=sa.Text(),
            nullable=True,
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("email", sa.String(length=254), nullable=False)
        )
        batch_op.drop_index("ix_users_email_lookup_hash")
        batch_op.alter_column(
            "email_lookup_hash",
            existing_type=sa.String(length=64),
            nullable=True,
        )
        batch_op.alter_column(
            "email_encrypted",
            existing_type=sa.Text(),
            nullable=True,
        )
        batch_op.create_index("ix_users_email", ["email"], unique=True)
