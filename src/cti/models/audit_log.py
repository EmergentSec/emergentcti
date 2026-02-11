import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    action: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(), server_default=sa.func.now()
    )

    user = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}:{self.entity_id}>"
