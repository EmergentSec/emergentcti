import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin, UUIDMixin


class CorrelationActionType(enum.StrEnum):
    link_threat_actor = "link_threat_actor"
    link_campaign = "link_campaign"
    map_technique = "map_technique"


class CorrelationRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "correlation_rules"

    name: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    # Match conditions - all nullable, rule matches if ALL non-null conditions match (AND logic)
    match_type: Mapped[str | None] = mapped_column(String(64), default=None)
    match_value_pattern: Mapped[str | None] = mapped_column(String(512), default=None)
    match_tags: Mapped[list | None] = mapped_column(JSONB, default=None)
    match_tlp: Mapped[str | None] = mapped_column(String(32), default=None)
    match_confidence_min: Mapped[int | None] = mapped_column(Integer, default=None)
    match_feed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="SET NULL"), default=None
    )

    # Action fields
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_threat_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="SET NULL"), default=None
    )
    target_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), default=None
    )
    target_technique_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attack_techniques.id", ondelete="SET NULL"), default=None
    )

    def __repr__(self) -> str:
        return f"<CorrelationRule {self.name} action={self.action_type} enabled={self.enabled}>"


class CorrelationEvent(UUIDMixin, Base):
    __tablename__ = "correlation_events"
    __table_args__ = (
        Index("ix_correlation_event_rule_id", "rule_id"),
        Index("ix_correlation_event_observable_id", "observable_id"),
        Index("ix_correlation_event_correlated_at", "correlated_at"),
    )

    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("correlation_rules.id", ondelete="SET NULL"), default=None
    )
    observable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("observables.id", ondelete="CASCADE")
    )
    action_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[uuid.UUID] = mapped_column()
    correlated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    source: Mapped[str] = mapped_column(String(32))

    def __repr__(self) -> str:
        return (
            f"<CorrelationEvent rule={self.rule_id}"
            f" observable={self.observable_id} source={self.source}>"
        )
