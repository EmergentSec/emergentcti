import enum
from datetime import datetime

from sqlalchemy import Boolean, Enum, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, UUIDMixin


class UserRole(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    readonly = "readonly"


class AuthProvider(str, enum.Enum):
    local = "local"
    azure_ad = "azure_ad"
    google = "google"
    oidc = "oidc"


class User(UUIDMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("auth_provider", "external_id", name="uq_user_provider_external_id"),
    )

    username: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(256), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    api_key: Mapped[str | None] = mapped_column(String(64), unique=True, default=None)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.readonly)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider), default=AuthProvider.local, server_default="local"
    )
    external_id: Mapped[str | None] = mapped_column(String(256), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), default=None)

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"
