"""Create schema for v0.7.3 baseline."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_current_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("unclassified_sections", sa.JSON(), nullable=False),
        sa.Column("document_warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "clauses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("clause_id", sa.String(length=50), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("marker", sa.String(length=50), nullable=False),
        sa.Column("clause_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "clause_id", name="uq_clauses_document_clause"),
    )
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "analysis_result_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("analysis_job_id", sa.String(length=36), nullable=False),
        sa.Column("clause_record_id", sa.String(length=36), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=False),
        sa.Column("display_label", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("expert_review_recommended", sa.Boolean(), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_job_id"], ["analysis_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["clause_record_id"], ["clauses.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "extractions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("filename_display", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("requires_user_review", sa.Boolean(), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "extraction_pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("extraction_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("requires_user_review", sa.Boolean(), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("extraction_id", "page_number", name="uq_extraction_pages_number"),
    )

    op.create_index("ix_clauses_document_id", "clauses", ["document_id"])
    op.create_index("ix_analysis_jobs_document_id", "analysis_jobs", ["document_id"])
    op.create_index("ix_analysis_result_items_analysis_job_id", "analysis_result_items", ["analysis_job_id"])
    op.create_index("ix_analysis_result_items_clause_record_id", "analysis_result_items", ["clause_record_id"])
    op.create_index("ix_analysis_result_items_reference_id", "analysis_result_items", ["reference_id"])
    op.create_index("ix_extraction_pages_extraction_id", "extraction_pages", ["extraction_id"])
    op.create_index("ix_clauses_reference_id", "clauses", ["reference_id"], unique=True)


def downgrade() -> None:
    op.drop_table("extraction_pages")
    op.drop_table("extractions")
    op.drop_table("analysis_result_items")
    op.drop_table("analysis_jobs")
    op.drop_table("clauses")
    op.drop_table("documents")
