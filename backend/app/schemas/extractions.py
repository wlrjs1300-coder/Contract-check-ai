from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExtractionPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    extraction_method: str
    text: str
    warnings: list[str]
    requires_user_review: bool


class ExtractionResponse(BaseModel):
    extraction_id: str
    filename_display: str
    source_type: str
    size_bytes: int
    page_count: int
    extraction_status: str
    extraction_method: str
    pages: list[ExtractionPageResponse]
    warnings: list[str]
    requires_user_review: bool
    created_at: datetime


class ExtractionErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ExtractionErrorResponse(BaseModel):
    detail: ExtractionErrorDetail
