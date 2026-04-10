from __future__ import annotations

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(sa.String(256), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        sa.Enum(UserRole, name="userrole"),
        nullable=False,
        default=UserRole.user,
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User(username={self.username!r}, role={self.role}, active={self.is_active})>"
