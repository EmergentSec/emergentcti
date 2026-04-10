from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, nullable=False, server_default=sa.func.now()
    )
    revoked: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    def __repr__(self) -> str:
        return f"<RefreshToken(user_id={self.user_id!r}, revoked={self.revoked})>"
