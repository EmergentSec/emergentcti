from sqlalchemy import Boolean, Enum, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, TimestampMixin, UUIDMixin
from cti.models.user import AuthProvider, UserRole


class SSOProviderConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sso_provider_configs"

    provider_type: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider), unique=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    client_secret_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, default=None
    )
    default_role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.readonly
    )
    allowed_domains: Mapped[list | None] = mapped_column(JSONB, default=None)
    auto_create_users: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<SSOProviderConfig {self.provider_type.value} ({self.display_name})>"
