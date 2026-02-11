import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin, UUIDMixin


class EnrichmentRunStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failure = "failure"


class EnrichmentConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "enrichment_configs"
    __table_args__ = (
        UniqueConstraint("provider_name", name="uq_enrichment_config_provider"),
    )

    provider_name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_enrich: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, default=None
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)

    def __repr__(self) -> str:
        return f"<EnrichmentConfig {self.provider_name} enabled={self.enabled}>"


class EnrichmentRun(UUIDMixin, Base):
    __tablename__ = "enrichment_runs"
    __table_args__ = (
        Index("ix_enrichment_run_obs_provider", "observable_id", "provider_name"),
        Index("ix_enrichment_run_created_at", "created_at"),
    )

    observable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("observables.id", ondelete="CASCADE")
    )
    provider_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[EnrichmentRunStatus] = mapped_column(
        Enum(EnrichmentRunStatus, name="enrichmentrunstatus"),
        default=EnrichmentRunStatus.pending,
    )
    result_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<EnrichmentRun {self.provider_name} "
            f"observable={self.observable_id} status={self.status.value}>"
        )
