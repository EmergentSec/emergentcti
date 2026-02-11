import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, String, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin


class CampaignStatus(enum.StrEnum):
    active = "active"
    historical = "historical"
    suspected = "suspected"


campaign_observables = Table(
    "campaign_observables",
    Base.metadata,
    Column(
        "campaign_id",
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "observable_id",
        UUID(as_uuid=True),
        ForeignKey("observables.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", server_default=func.now()),
)


class Campaign(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("ix_campaign_name", "name"),
        Index("ix_campaign_status", "status"),
        Index("ix_campaign_threat_actor_id", "threat_actor_id"),
    )

    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    threat_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("threat_actors.id", ondelete="SET NULL"),
        default=None,
    )
    status: Mapped[str] = mapped_column(String(32), default="suspected")
    first_seen: Mapped[datetime | None] = mapped_column(default=None)
    last_seen: Mapped[datetime | None] = mapped_column(default=None)
    tlp: Mapped[str] = mapped_column(String(16), default="clear")
    objective: Mapped[str | None] = mapped_column(Text, default=None)
    external_references: Mapped[list | None] = mapped_column(JSONB, default=None)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    threat_actor = relationship("ThreatActor", lazy="selectin")
    observables = relationship(
        "Observable",
        secondary=campaign_observables,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.name}>"
