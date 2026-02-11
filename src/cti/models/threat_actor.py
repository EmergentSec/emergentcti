import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Index, String, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin

threat_actor_observables = Table(
    "threat_actor_observables",
    Base.metadata,
    Column(
        "threat_actor_id",
        UUID(as_uuid=True),
        ForeignKey("threat_actors.id", ondelete="CASCADE"),
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

threat_actor_techniques = Table(
    "threat_actor_techniques",
    Base.metadata,
    Column(
        "threat_actor_id",
        UUID(as_uuid=True),
        ForeignKey("threat_actors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technique_id",
        UUID(as_uuid=True),
        ForeignKey("attack_techniques.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("created_at", server_default=func.now()),
)


class ThreatActor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "threat_actors"
    __table_args__ = (
        Index("ix_threat_actor_name", "name"),
        Index("ix_threat_actor_country", "country"),
    )

    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    aliases: Mapped[list | None] = mapped_column(JSONB, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    motivation: Mapped[str | None] = mapped_column(String(128), default=None)
    sophistication: Mapped[str | None] = mapped_column(String(64), default=None)
    country: Mapped[str | None] = mapped_column(String(64), default=None)
    first_seen: Mapped[datetime | None] = mapped_column(default=None)
    last_seen: Mapped[datetime | None] = mapped_column(default=None)
    tlp: Mapped[str] = mapped_column(String(16), default="clear")
    external_references: Mapped[list | None] = mapped_column(JSONB, default=None)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    observables = relationship(
        "Observable",
        secondary=threat_actor_observables,
        lazy="selectin",
    )
    techniques = relationship(
        "AttackTechnique",
        secondary=threat_actor_techniques,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ThreatActor {self.name}>"
