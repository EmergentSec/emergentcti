from __future__ import annotations

import enum
import uuid

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin, UUIDMixin
from cti.models.observable import ObservableType


class ExportFormat(str, enum.Enum):
    TEXT = "text"
    JSON = "json"


class ExportProfile(UUIDMixin, TimestampMixin, Base):
    """Saved, shared export filters evaluated against current data and policy."""

    __tablename__ = "export_profiles"
    __table_args__ = (
        CheckConstraint("format IN ('text', 'json')", name="ck_export_profile_format"),
        CheckConstraint(
            "confidence_min >= 0 AND confidence_min <= 100",
            name="ck_export_profile_confidence_min",
        ),
        CheckConstraint(
            "max_age_days IS NULL OR (max_age_days >= 1 AND max_age_days <= 36500)",
            name="ck_export_profile_max_age_days",
        ),
        Index("ix_export_profile_feed_id", "feed_id"),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    format: Mapped[ExportFormat] = mapped_column(
        Enum(
            ExportFormat,
            values_callable=lambda x: [e.value for e in x],
            native_enum=False,
            length=16,
        ),
    )
    type: Mapped[ObservableType | None] = mapped_column(
        Enum(ObservableType, values_callable=lambda x: [e.value for e in x]),
        default=None,
    )
    confidence_min: Mapped[int] = mapped_column(Integer, default=70)
    max_age_days: Mapped[int | None] = mapped_column(Integer, default=None)
    # RESTRICT: deleting a feed must never silently broaden a profile to "all feeds".
    feed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="RESTRICT"), default=None
    )

    def __repr__(self) -> str:
        return f"<ExportProfile(name={self.name!r}, format={self.format!r})>"
