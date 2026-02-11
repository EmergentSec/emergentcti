import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cti.models.feed import Feed
    from cti.models.tag import Tag


class ObservableType(str, enum.Enum):
    ip_addr = "ip-addr"
    domain_name = "domain-name"
    url = "url"
    file_hash = "file-hash"
    email_addr = "email-addr"
    command_line = "command-line"
    user_agent = "user-agent"
    certificate = "certificate"
    asn = "asn"
    cidr = "cidr"


observable_tags = Table(
    "observable_tags",
    Base.metadata,
    Column("observable_id", UUID(as_uuid=True), ForeignKey("observables.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

observable_sources = Table(
    "observable_sources",
    Base.metadata,
    Column("observable_id", UUID(as_uuid=True), ForeignKey("observables.id", ondelete="CASCADE"), primary_key=True),
    Column("feed_id", UUID(as_uuid=True), ForeignKey("feeds.id", ondelete="CASCADE"), primary_key=True),
)


class Observable(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "observables"
    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_observable_type_value"),
        Index("ix_observable_type", "type"),
        Index("ix_observable_value", "value"),
        Index("ix_observable_last_seen", "last_seen"),
    )

    type: Mapped[ObservableType] = mapped_column(Enum(ObservableType, values_callable=lambda x: [e.value for e in x]))
    value: Mapped[str] = mapped_column(String(2048))
    confidence_score: Mapped[int] = mapped_column(Integer, default=50)
    first_seen: Mapped[datetime | None] = mapped_column(default=None)
    last_seen: Mapped[datetime | None] = mapped_column(default=None)
    tlp: Mapped[str] = mapped_column(String(16), default="clear")
    context: Mapped[dict | None] = mapped_column(JSONB, default=None)
    category: Mapped[str | None] = mapped_column(String(64), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    external_references: Mapped[list | None] = mapped_column(JSONB, default=None)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tags: Mapped[list["Tag"]] = relationship(secondary=observable_tags, lazy="selectin")
    sources: Mapped[list["Feed"]] = relationship(secondary=observable_sources, lazy="selectin")

    def __repr__(self) -> str:
        return f"<Observable {self.type.value}:{self.value}>"
