from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from cti.models.feed import Feed
    from cti.models.observable import Observable


class ObservableSource(UUIDMixin, Base):
    __tablename__ = "observable_sources"
    __table_args__ = (
        UniqueConstraint("observable_id", "feed_id", name="uq_observable_source"),
        Index("ix_observable_source_feed_id", "feed_id"),
        Index("ix_observable_source_observable_id", "observable_id"),
    )

    observable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("observables.id", ondelete="CASCADE"),
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feeds.id", ondelete="CASCADE"),
    )
    source_confidence: Mapped[int] = mapped_column(Integer, default=50)
    first_seen_by_feed: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_by_feed: Mapped[datetime] = mapped_column(server_default=func.now())

    observable: Mapped[Observable] = relationship(back_populates="sources")
    feed: Mapped[Feed] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ObservableSource(observable_id={self.observable_id!r}, "
            f"feed_id={self.feed_id!r}, confidence={self.source_confidence})>"
        )
