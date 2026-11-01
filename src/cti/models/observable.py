from __future__ import annotations

import enum
import uuid  # noqa: TC003 - SQLAlchemy resolves mapped annotations at runtime.
from datetime import datetime  # noqa: TC003 - SQLAlchemy resolves mapped annotations at runtime.
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin
from cti.models.tag import observable_tags
from cti.models.tlp import TLP_COLUMN_LENGTH, tlp_check_sql

if TYPE_CHECKING:
    from cti.models.observable_source import ObservableSource
    from cti.models.tag import Tag
    from cti.models.user import User


class ObservableType(enum.StrEnum):
    IP_ADDR = "ip-addr"
    DOMAIN_NAME = "domain-name"
    URL = "url"
    FILE_HASH = "file-hash"
    EMAIL_ADDR = "email-addr"
    COMMAND_LINE = "command-line"


class Observable(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "observables"
    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_observable_type_value"),
        CheckConstraint(
            "manual_confidence IS NULL OR (manual_confidence >= 0 AND manual_confidence <= 100)",
            name="ck_observables_manual_confidence",
        ),
        CheckConstraint(
            "confidence_override IS NULL OR "
            "(confidence_override >= 0 AND confidence_override <= 100)",
            name="ck_observables_confidence_override",
        ),
        CheckConstraint(
            "confidence_override IS NOT NULL OR override_set_at IS NULL",
            name="ck_observables_override_set_at",
        ),
        CheckConstraint(tlp_check_sql("manual_tlp"), name="ck_observables_manual_tlp"),
        CheckConstraint(tlp_check_sql("tlp_override"), name="ck_observables_tlp_override"),
        CheckConstraint(
            "(tlp_override IS NULL AND tlp_override_reason IS NULL "
            "AND tlp_override_set_at IS NULL) OR "
            "(tlp_override IS NOT NULL AND tlp_override_reason IS NOT NULL "
            "AND tlp_override_set_at IS NOT NULL)",
            name="ck_observables_tlp_override_fields",
        ),
        Index("ix_observable_type", "type"),
        Index("ix_observable_value", "value"),
        Index("ix_observable_confidence", "confidence_score"),
        Index("ix_observable_last_seen", "last_seen"),
        Index(
            "ix_observable_type_confidence_lastseen",
            "type",
            "confidence_score",
            "last_seen",
        ),
    )

    type: Mapped[ObservableType] = mapped_column(
        Enum(ObservableType, values_callable=lambda x: [e.value for e in x]),
    )
    value: Mapped[str] = mapped_column(String(2048))
    confidence_score: Mapped[int] = mapped_column(Integer, default=50)
    manual_confidence: Mapped[int | None] = mapped_column(Integer, default=None)
    confidence_override: Mapped[int | None] = mapped_column(Integer, default=None)
    override_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    override_set_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            name="fk_observables_override_set_by_id",
            ondelete="SET NULL",
        ),
        default=None,
    )
    # TLP (#15). NULL = Unspecified. The effective marking is never stored; it
    # is derived at read time by cti.services.tlp.
    manual_tlp: Mapped[str | None] = mapped_column(String(TLP_COLUMN_LENGTH), default=None)
    tlp_override: Mapped[str | None] = mapped_column(String(TLP_COLUMN_LENGTH), default=None)
    tlp_override_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    tlp_override_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    tlp_override_set_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            name="fk_observables_tlp_override_set_by_id",
            ondelete="SET NULL",
        ),
        default=None,
    )
    first_seen: Mapped[datetime | None] = mapped_column(default=None)
    last_seen: Mapped[datetime | None] = mapped_column(default=None)

    sources: Mapped[list[ObservableSource]] = relationship(
        back_populates="observable",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    override_set_by: Mapped[User | None] = relationship(
        foreign_keys=[override_set_by_id],
        lazy="selectin",
    )
    tlp_override_set_by: Mapped[User | None] = relationship(
        foreign_keys=[tlp_override_set_by_id],
        lazy="selectin",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary=observable_tags,
        lazy="selectin",
        order_by="Tag.name",
    )

    def __repr__(self) -> str:
        return (
            f"<Observable(type={self.type!r}, value={self.value!r}, "
            f"confidence={self.confidence_score})>"
        )
