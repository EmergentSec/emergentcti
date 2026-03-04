from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from cti.models.observable_source import ObservableSource


class ObservableType(str, enum.Enum):
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
    first_seen: Mapped[datetime | None] = mapped_column(default=None)
    last_seen: Mapped[datetime | None] = mapped_column(default=None)

    sources: Mapped[list[ObservableSource]] = relationship(
        back_populates="observable",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Observable(type={self.type!r}, value={self.value!r}, confidence={self.confidence_score})>"
