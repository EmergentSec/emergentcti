import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    report_type: str  # "threat_summary" | "observable_report" | "campaign_brief"
    parameters: dict = Field(default_factory=dict)
    format: str = "html"  # "pdf" | "html"


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    report_type: str
    parameters: dict
    status: str
    format: str
    file_path: str | None
    generated_by: uuid.UUID | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int
