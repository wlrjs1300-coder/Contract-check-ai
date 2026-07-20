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
    created_at: datetime
    updated_at: datetime | None = None


class ExtractionErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    analysis_blocked: bool = True


class ExtractionErrorResponse(BaseModel):
    detail: ExtractionErrorDetail
