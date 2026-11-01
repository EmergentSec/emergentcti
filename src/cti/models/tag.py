"""Flat tags for observables and reports (#15)."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - SQLAlchemy resolves mapped annotations at runtime.

from sqlalchemy import Column, ForeignKey, Index, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, UUIDMixin

TAG_NAME_MAX_LENGTH = 50


class Tag(UUIDMixin, Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(TAG_NAME_MAX_LENGTH), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<Tag(name={self.name!r})>"


observable_tags = Table(
    "observable_tags",
    Base.metadata,
    Column("observable_id", ForeignKey("observables.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_observable_tags_tag_id", "tag_id"),
)

report_tags = Table(
    "report_tags",
    Base.metadata,
    Column("report_id", ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_report_tags_tag_id", "tag_id"),
)

# RESTRICT on the tag side: deleting a tag a profile filters on would silently
# broaden that profile, so the delete is refused (409), like referenced feeds.
export_profile_tags = Table(
    "export_profile_tags",
    Base.metadata,
    Column(
        "export_profile_id",
        ForeignKey("export_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True),
    Index("ix_export_profile_tags_tag_id", "tag_id"),
)
