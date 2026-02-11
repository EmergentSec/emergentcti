import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin, UUIDMixin


class AlertRule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "alert_rules"

    name: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    # Match conditions - all nullable, rule matches if ALL non-null conditions match (AND logic)
    match_type: Mapped[str | None] = mapped_column(String(64), default=None)
    match_value_pattern: Mapped[str | None] = mapped_column(String(1024), default=None)
    match_tags: Mapped[list | None] = mapped_column(JSONB, default=None)
    match_tlp: Mapped[str | None] = mapped_column(String(16), default=None)
    match_confidence_min: Mapped[int | None] = mapped_column(Integer, default=None)
    match_feed_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feeds.id", ondelete="SET NULL"), default=None
    )

    # Notification configuration
    notification_channels: Mapped[list] = mapped_column(JSONB, default=list)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_triggered_at: Mapped[datetime | None] = mapped_column(default=None)

    def __repr__(self) -> str:
        return f"<AlertRule {self.name} enabled={self.enabled}>"


class AlertEvent(UUIDMixin, Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_event_rule_id", "rule_id"),
        Index("ix_alert_event_observable_id", "observable_id"),
        Index("ix_alert_event_triggered_at", "triggered_at"),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE")
    )
    observable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("observables.id", ondelete="CASCADE")
    )
    triggered_at: Mapped[datetime] = mapped_column(server_default=func.now())
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_error: Mapped[str | None] = mapped_column(Text, default=None)

    def __repr__(self) -> str:
        return f"<AlertEvent rule={self.rule_id} observable={self.observable_id}>"


class WebhookConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "webhook_configs"

    name: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(String(2048))
    secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    events: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    def __repr__(self) -> str:
        return f"<WebhookConfig {self.name} enabled={self.enabled}>"
