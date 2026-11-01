# ruff: noqa: TC003
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin
from cti.models.tag import report_tags
from cti.models.tlp import TLP_COLUMN_LENGTH, tlp_check_sql

if TYPE_CHECKING:
    from cti.models.observable import Observable
    from cti.models.tag import Tag
    from cti.models.user import User


class ReportOrigin(enum.StrEnum):
    PROVIDER = "provider"
    INTERNAL = "internal"


class ContentFormat(enum.StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"


report_observables = Table(
    "report_observables",
    Base.metadata,
    Column(
        "report_id",
        ForeignKey("reports.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "observable_id",
        ForeignKey("observables.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", DateTime(), nullable=False, server_default=func.now()),
    # Import attribution (#14). All null for manual links from #12.
    Column("imported_at", DateTime(), nullable=True),
    Column(
        "imported_by_id",
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("analyst_confidence", Integer(), nullable=True),
    Column("source_excerpt", String(500), nullable=True),
    CheckConstraint(
        "analyst_confidence IS NULL OR (analyst_confidence >= 0 AND analyst_confidence <= 100)",
        name="ck_report_observables_analyst_confidence",
    ),
    Index("ix_report_observables_observable_id", "observable_id"),
)


class Report(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("origin IN ('provider', 'internal')", name="ck_reports_origin"),
        CheckConstraint(
            "content_format IN ('markdown', 'text')",
            name="ck_reports_content_format",
        ),
        CheckConstraint(
            "is_ai_generated OR "
            "(ai_provider IS NULL AND ai_model IS NULL AND ai_generated_at IS NULL)",
            name="ck_reports_ai_provenance",
        ),
        CheckConstraint(tlp_check_sql("tlp"), name="ck_reports_tlp"),
        Index("ix_reports_published_at", "published_at"),
        Index("ix_reports_origin", "origin"),
        Index("ix_reports_source_name", "source_name"),
        Index("ix_reports_created_at", "created_at"),
    )

    title: Mapped[str] = mapped_column(String(500))
    origin: Mapped[ReportOrigin] = mapped_column(
        Enum(
            ReportOrigin,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=16,
        )
    )
    source_name: Mapped[str | None] = mapped_column(String(255), default=None)
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    source_url: Mapped[str | None] = mapped_column(String(2048), default=None)
    content: Mapped[str | None] = mapped_column(Text, default=None)
    content_format: Mapped[ContentFormat] = mapped_column(
        Enum(
            ContentFormat,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            length=16,
        ),
        default=ContentFormat.MARKDOWN,
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_provider: Mapped[str | None] = mapped_column(String(255), default=None)
    ai_model: Mapped[str | None] = mapped_column(String(255), default=None)
    ai_generated_at: Mapped[datetime | None] = mapped_column(default=None)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    # TLP (#15): the report's own marking (NULL = Unspecified); the attachment
    # inherits it.
    tlp: Mapped[str | None] = mapped_column(String(TLP_COLUMN_LENGTH), default=None)

    created_by: Mapped[User | None] = relationship(lazy="selectin")
    attachment: Mapped[ReportAttachment | None] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
        lazy="selectin",
    )
    observables: Mapped[list[Observable]] = relationship(
        secondary=report_observables,
        lazy="selectin",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=report_tags,
        lazy="selectin",
        order_by="Tag.name",
    )


class ReportAttachment(UUIDMixin, Base):
    __tablename__ = "report_attachments"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_report_attachments_size_bytes"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"),
        unique=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(CHAR(64))
    content: Mapped[bytes] = deferred(mapped_column(LargeBinary))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    report: Mapped[Report] = relationship(back_populates="attachment")
