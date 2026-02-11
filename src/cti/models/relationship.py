import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from cti.models.observable import Observable


class RelationshipType(enum.StrEnum):
    resolves_to = "resolves-to"
    contains = "contains"
    communicates_with = "communicates-with"
    drops = "drops"
    downloads = "downloads"
    associated_with = "associated-with"
    belongs_to = "belongs-to"
    hosts = "hosts"
    delivers = "delivers"
    indicates = "indicates"
    related_to = "related-to"


class ObservableRelationship(UUIDMixin, Base):
    __tablename__ = "observable_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "target_id",
            "relationship_type",
            name="uq_relationship_src_tgt_type",
        ),
        Index("ix_relationship_source_id", "source_id"),
        Index("ix_relationship_target_id", "target_id"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("observables.id", ondelete="CASCADE")
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("observables.id", ondelete="CASCADE")
    )
    relationship_type: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[int] = mapped_column(Integer, default=50)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), default=None
    )

    source: Mapped["Observable"] = relationship(
        "Observable", foreign_keys=[source_id], lazy="joined"
    )
    target: Mapped["Observable"] = relationship(
        "Observable", foreign_keys=[target_id], lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<Relationship {self.source_id} "
            f"-{self.relationship_type}-> {self.target_id}>"
        )
