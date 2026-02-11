import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin


class FeedType(str, enum.Enum):
    api = "api"
    taxii = "taxii"
    file = "file"
    scraper = "scraper"


class FeedRunStatus(str, enum.Enum):
    running = "running"
    success = "success"
    failure = "failure"


class Feed(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "feeds"

    name: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    feed_type: Mapped[FeedType] = mapped_column(Enum(FeedType))
    url: Mapped[str | None] = mapped_column(String(2048), default=None)
    config: Mapped[dict | None] = mapped_column(JSONB, default=None)
    schedule_cron: Mapped[str | None] = mapped_column(String(64), default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_config_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    default_ttl_days: Mapped[int | None] = mapped_column(Integer, default=None)
    last_run_at: Mapped[datetime | None] = mapped_column(default=None)

    runs: Mapped[list["FeedRun"]] = relationship(back_populates="feed", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Feed {self.name} ({self.feed_type.value})>"


class FeedRun(UUIDMixin, Base):
    __tablename__ = "feed_runs"

    feed_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feeds.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    status: Mapped[FeedRunStatus] = mapped_column(Enum(FeedRunStatus), default=FeedRunStatus.running)
    observables_ingested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    feed: Mapped["Feed"] = relationship(back_populates="runs")

    def __repr__(self) -> str:
        return f"<FeedRun {self.feed_id} {self.status.value}>"
