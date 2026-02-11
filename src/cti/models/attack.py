import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, UUIDMixin

attack_technique_tactics = Table(
    "attack_technique_tactics",
    Base.metadata,
    Column(
        "technique_id",
        UUID(as_uuid=True),
        ForeignKey("attack_techniques.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tactic_id",
        UUID(as_uuid=True),
        ForeignKey("attack_tactics.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class AttackTactic(UUIDMixin, Base):
    __tablename__ = "attack_tactics"
    __table_args__ = (
        Index("ix_attack_tactic_external_id", "external_id"),
        Index("ix_attack_tactic_order", "order"),
    )

    external_id: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    url: Mapped[str | None] = mapped_column(String(1024), default=None)
    short_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    techniques: Mapped[list["AttackTechnique"]] = relationship(
        "AttackTechnique",
        secondary=attack_technique_tactics,
        back_populates="tactics",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AttackTactic {self.external_id}: {self.name}>"


class AttackTechnique(UUIDMixin, Base):
    __tablename__ = "attack_techniques"
    __table_args__ = (
        Index("ix_attack_technique_external_id", "external_id"),
        Index("ix_attack_technique_parent_id", "parent_id"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    is_subtechnique: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attack_techniques.id", ondelete="SET NULL"),
        default=None,
    )
    url: Mapped[str | None] = mapped_column(String(1024), default=None)

    parent: Mapped["AttackTechnique | None"] = relationship(
        "AttackTechnique",
        remote_side="AttackTechnique.id",
        lazy="joined",
    )
    tactics: Mapped[list[AttackTactic]] = relationship(
        "AttackTactic",
        secondary=attack_technique_tactics,
        back_populates="techniques",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AttackTechnique {self.external_id}: {self.name}>"


class ObservableTechnique(UUIDMixin, Base):
    __tablename__ = "observable_attack_techniques"
    __table_args__ = (
        UniqueConstraint(
            "observable_id",
            "technique_id",
            name="uq_observable_technique",
        ),
        Index(
            "ix_obs_technique_observable_id", "observable_id"
        ),
        Index(
            "ix_obs_technique_technique_id", "technique_id"
        ),
    )

    observable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("observables.id", ondelete="CASCADE"),
        nullable=False,
    )
    technique_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attack_techniques.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )

    technique: Mapped[AttackTechnique] = relationship(
        "AttackTechnique", lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<ObservableTechnique "
            f"obs={self.observable_id} "
            f"tech={self.technique_id}>"
        )
