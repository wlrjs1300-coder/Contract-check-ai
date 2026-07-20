from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    character_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50))
    unclassified_sections: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
    )
    document_warnings: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    clauses: Mapped[list[Clause]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    analysis_jobs: Mapped[list[AnalysisJob]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Clause(Base):
    __tablename__ = "clauses"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "clause_id",
            name="uq_clauses_document_clause",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    clause_id: Mapped[str] = mapped_column(String(50))
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    reference_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )
    source_hash: Mapped[str] = mapped_column(String(64))
    ordinal: Mapped[int] = mapped_column(Integer)
    marker: Mapped[str] = mapped_column(String(50))
    clause_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    warnings: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
    )

    document: Mapped[Document] = relationship(back_populates="clauses")
    analysis_result_items: Mapped[list[AnalysisResultItem]] = relationship(
        back_populates="clause",
        cascade="all, delete-orphan",
    )


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    document: Mapped[Document] = relationship(
        back_populates="analysis_jobs",
    )
    result_items: Mapped[list[AnalysisResultItem]] = relationship(
        back_populates="analysis_job",
        cascade="all, delete-orphan",
    )


class AnalysisResultItem(Base):
    __tablename__ = "analysis_result_items"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    analysis_job_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        index=True,
    )
    clause_record_id: Mapped[str] = mapped_column(
        ForeignKey("clauses.id", ondelete="CASCADE"),
        index=True,
    )
    reference_id: Mapped[str] = mapped_column(String(100), index=True)
    display_label: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    expert_review_recommended: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )

    analysis_job: Mapped[AnalysisJob] = relationship(
        back_populates="result_items",
    )
    clause: Mapped[Clause] = relationship(
        back_populates="analysis_result_items",
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename_display: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(20))
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50))
    method: Mapped[str] = mapped_column(String(20))
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    requires_user_review: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    pages: Mapped[list[ExtractionPage]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
    )


class ExtractionPage(Base):
    __tablename__ = "extraction_pages"
    __table_args__ = (
        UniqueConstraint(
            "extraction_id",
            "page_number",
            name="uq_extraction_pages_number",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    extraction_id: Mapped[str] = mapped_column(
        ForeignKey("extractions.id", ondelete="CASCADE"),
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    requires_user_review: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )

    extraction: Mapped[Extraction] = relationship(back_populates="pages")
