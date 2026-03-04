from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin


class FeedType(str, enum.Enum):
    API = "api"
    FILE = "file"
    SCRAPER = "scraper"


class FeedRunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"


class Feed(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "feeds"

    name: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    feed_type: Mapped[FeedType] = mapped_column(
        Enum(FeedType, values_callable=lambda x: [e.value for e in x]),
    )
    url: Mapped[str | None] = mapped_column(String(2048), default=None)
    config: Mapped[dict | None] = mapped_column(JSONB, default=None)
    schedule_cron: Mapped[str | None] = mapped_column(String(64), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_preconfigured: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_config_encrypted: Mapped[bytes | None] = mapped_column(default=None)
    default_confidence: Mapped[int] = mapped_column(Integer, default=50)
    last_run_at: Mapped[datetime | None] = mapped_column(default=None)

    runs: Mapped[list[FeedRun]] = relationship(
        back_populates="feed",
        lazy="selectin",
        order_by="FeedRun.started_at.desc()",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Feed(name={self.name!r}, type={self.feed_type!r}, enabled={self.enabled})>"


class FeedRun(UUIDMixin, Base):
    __tablename__ = "feed_runs"

    feed_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feeds.id", ondelete="CASCADE"),
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    status: Mapped[FeedRunStatus] = mapped_column(
        Enum(FeedRunStatus, values_callable=lambda x: [e.value for e in x]),
        default=FeedRunStatus.RUNNING,
    )
    observables_ingested: Mapped[int] = mapped_column(Integer, default=0)
    observables_new: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    feed: Mapped[Feed] = relationship(back_populates="runs")

    def __repr__(self) -> str:
        return f"<FeedRun(feed_id={self.feed_id!r}, status={self.status!r}, ingested={self.observables_ingested})>"
