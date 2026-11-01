# ruff: noqa: TC003
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, Enum, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin


class AiProvider(enum.StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    XAI = "xai"


class AiProviderConfig(TimestampMixin, Base):
    __tablename__ = "ai_providers"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('anthropic', 'openai', 'openrouter', 'xai')",
            name="ck_ai_providers_provider",
        ),
        CheckConstraint(
            "last_check_status IS NULL OR last_check_status IN ('ok', 'error')",
            name="ck_ai_providers_last_check_status",
        ),
        CheckConstraint(
            "last_check_category IS NULL OR last_check_category IN "
            "('invalid_credentials', 'permission_denied', 'rate_limited', "
            "'insufficient_quota', 'model_unavailable', 'timeout', 'network_error', "
            "'provider_error', 'not_configured')",
            name="ck_ai_providers_last_check_category",
        ),
    )

    provider: Mapped[AiProvider] = mapped_column(
        Enum(
            AiProvider,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            create_constraint=False,
            length=32,
        ),
        primary_key=True,
    )
    credentials_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    key_hint: Mapped[str | None] = mapped_column(String(8), default=None)
    model_cache: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, default=None)
    models_fetched_at: Mapped[datetime | None] = mapped_column(default=None)
    last_check_status: Mapped[str | None] = mapped_column(String(16), default=None)
    last_check_category: Mapped[str | None] = mapped_column(String(32), default=None)
    last_checked_at: Mapped[datetime | None] = mapped_column(default=None)


class AiSettingsRecord(Base):
    __tablename__ = "ai_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_ai_settings_singleton"),
        CheckConstraint(
            "default_provider IS NULL OR default_model IS NOT NULL",
            name="ck_ai_settings_default_pair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    default_provider: Mapped[AiProvider | None] = mapped_column(
        Enum(
            AiProvider,
            values_callable=lambda values: [value.value for value in values],
            native_enum=False,
            create_constraint=False,
            length=32,
        ),
        ForeignKey("ai_providers.provider", ondelete="SET NULL"),
        default=None,
    )
    default_model: Mapped[str | None] = mapped_column(String(255), default=None)
    default_model_is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )
