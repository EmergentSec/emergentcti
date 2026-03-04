from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, UUIDMixin


class ApiKey(UUIDMixin, Base):
    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(128))
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    def __repr__(self) -> str:
        return f"<ApiKey(name={self.name!r}, prefix={self.key_prefix!r}, active={self.is_active})>"
