"""Add users table and ownership references for documents/extractions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_auth_ownership"
down_revision = "0001_current_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not (inspector.has_table("documents") and inspector.has_table("extractions")):
        raise RuntimeError(
            "Legacy development data must be cleared before ownership migration."
        )

    has_document_rows = (
        connection.execute(sa.text("SELECT 1 FROM documents LIMIT 1")).first()
        is not None
    )
    has_extraction_rows = (
        connection.execute(sa.text("SELECT 1 FROM extractions LIMIT 1")).first()
        is not None
    )
    if has_document_rows or has_extraction_rows:
        raise RuntimeError(
            "Legacy development data must be cleared before ownership migration."
        )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("auth_version >= 1", name="ck_users_auth_version_positive"),
    )
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
    )

    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "owner_id",
                sa.String(length=36),
                nullable=False,
            )
        )
        batch_op.create_index("ix_documents_owner_id", ["owner_id"])
        batch_op.create_foreign_key(
            "fk_documents_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("extractions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "owner_id",
                sa.String(length=36),
                nullable=False,
            )
        )
        batch_op.create_index("ix_extractions_owner_id", ["owner_id"])
        batch_op.create_foreign_key(
            "fk_extractions_owner_id_users",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.drop_constraint("fk_extractions_owner_id_users", type_="foreignkey")
        batch_op.drop_index("ix_extractions_owner_id")
        batch_op.drop_column("owner_id")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_owner_id_users", type_="foreignkey")
        batch_op.drop_index("ix_documents_owner_id")
        batch_op.drop_column("owner_id")
    op.drop_table("users")
