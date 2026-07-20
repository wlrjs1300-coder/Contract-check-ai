from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OcrBlockResponse(BaseModel):
    block_index: int
    text: str
    confidence: float | None = None
    bbox: tuple[int, int, int, int] | None = None
    reading_order: int


class ExtractionPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    extraction_method: str
    text: str
    text_length: int = 0
    page_id: str | None = None
    source_format: str | None = None
    normalized_width: int | None = None
    normalized_height: int | None = None
    blocks: list[OcrBlockResponse] = Field(default_factory=list)
    warnings: list[str]
    requires_user_review: bool
    review_required: bool = True
    analysis_blocked: bool = True
    review_status: str = "pending"
    review_version: int = 1
    reviewed_text: str | None = None
    text_changed: bool = False
    reviewed_at: str | None = None
    final_text_preview: str | None = None
    version: int = 1
    failure: str | None = None


class ExtractionResponse(BaseModel):
    extraction_id: str
    filename_display: str
    source_type: str
    size_bytes: int
    page_count: int
    total_pages: int = 0
    completed_pages: int = 0
    failed_pages: int = 0
    total_text_length: int = 0
    extraction_status: str
    extraction_method: str
    pages: list[ExtractionPageResponse]
    warnings: list[str]
    requires_user_review: bool
    review_required: bool = True
    analysis_blocked: bool = True
    review_status: str = "not_required"
    review_version: int = 1
    can_confirm: bool = False
    reviewed_pages: int = 0
    edited_pages: int = 0
    required_review_pages: int = 0
    failed_pages: int = 0
    blocking_reasons: list[str] = Field(default_factory=list)
    confirmed_at: str | None = None
    final_text_length: int = 0
    created_at: datetime
    updated_at: datetime | None = None


class ExtractionReviewPageResponse(BaseModel):
    page_id: str
    page_number: int
    method: str
    classification: str | None = None
    original_text: str
    reviewed_text: str | None = None
    final_text_preview: str | None = None
    text_changed: bool = False
    review_status: str = "pending"
    review_version: int = 1
    reviewed_at: str | None = None
    confirmed_at: str | None = None
    warnings: list[str] = Field(default_factory=list)
    blocks: list[OcrBlockResponse] = Field(default_factory=list)
    failure: str | None = None
    analysis_blocked: bool = True


class ExtractionReviewResponse(BaseModel):
    extraction_id: str
    review_status: str = "pending"
    review_version: int = 1
    review_required: bool
    can_confirm: bool = False
    review_completed: bool = False
    total_pages: int
    required_review_pages: int = 0
    reviewed_pages: int = 0
    edited_pages: int = 0
    failed_pages: int = 0
    blocked: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    pages: list[ExtractionReviewPageResponse]


class PageReviewPatchRequest(BaseModel):
    version: int | None = Field(default=None, ge=1)
    unchanged: bool | None = None
    reviewed_text: str | None = None


class ConfirmationSnapshotPage(BaseModel):
    page_id: str | None = None
    page_number: int
    final_text: str
    text_source: str
    text_changed: bool
    method: str
    warnings: list[str] = Field(default_factory=list)


class ExtractionConfirmationResponse(BaseModel):
    extraction_id: str
    extraction_status: str
    review_status: str
    review_version: int
    snapshot_version: int
    confirmed_at: str
    total_pages: int
    confirmed_pages: int
    changed_pages: int
    total_text_length: int
    confirmation_checksum: str
    snapshot: list[ConfirmationSnapshotPage]


class ExtractionErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    analysis_blocked: bool = True


class ExtractionErrorResponse(BaseModel):
    detail: ExtractionErrorDetail
