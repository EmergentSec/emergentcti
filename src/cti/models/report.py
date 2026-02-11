import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, UUIDMixin


class ReportType(StrEnum):
    threat_summary = "threat_summary"
    observable_report = "observable_report"
    campaign_brief = "campaign_brief"


class ReportStatus(StrEnum):
    pending = "pending"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class ReportFormat(StrEnum):
    pdf = "pdf"
    html = "html"


class Report(UUIDMixin, Base):
    __tablename__ = "reports"

    title: Mapped[str] = mapped_column(String(256))
    report_type: Mapped[str] = mapped_column(String(50))
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    format: Mapped[str] = mapped_column(String(10), default="pdf")
    file_path: Mapped[str | None] = mapped_column(String(512), default=None)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(default=None)

    def __repr__(self) -> str:
        return f"<Report {self.title} status={self.status}>"
