"""Add nullable encrypted scalar metadata columns."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_scalar_metadata_additive"
down_revision = "0003_scalar_field_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_encrypted", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_lookup_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("filename_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("filename_display_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "clauses",
        sa.Column("title_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("clauses") as batch_op:
        batch_op.drop_column("title_encrypted")
    with op.batch_alter_table("extractions") as batch_op:
        batch_op.drop_column("filename_display_encrypted")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("filename_encrypted")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("email_lookup_hash")
        batch_op.drop_column("email_encrypted")
