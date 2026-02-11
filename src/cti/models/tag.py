from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base, UUIDMixin


class Tag(UUIDMixin, Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    color: Mapped[str] = mapped_column(String(7), default="#6b7280")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"
