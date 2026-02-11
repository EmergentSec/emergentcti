import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base, TimestampMixin, UUIDMixin


class SavedSearch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "saved_searches"
    __table_args__ = (Index("ix_saved_search_user_id", "user_id"),)

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    is_shared: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    user = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<SavedSearch {self.name} (user={self.user_id})>"
