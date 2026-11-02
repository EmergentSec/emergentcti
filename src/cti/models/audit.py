"""Append-only audit history of sensitive changes and disclosures (issue #16).

The table deliberately has no foreign keys: deleting a user, API key, report,
or feed must neither delete nor null out the history that names it. Labels are
snapshots taken when the event was written. Write events through
:mod:`cti.services.audit`, never by constructing rows directly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from cti.models.base import Base


class ActorType(StrEnum):
    """Who performed the action."""

    USER = "user"
    API_KEY = "api_key"
    SYSTEM = "system"


class AuditOutcome(StrEnum):
    """What happened. ``initiated``/``completed``/``interrupted`` are for disclosures."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    INITIATED = "initiated"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


def _in_list(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(v.value) for v in values)})"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(_in_list("actor_type", ActorType), name="ck_audit_events_actor_type"),
        CheckConstraint(_in_list("outcome", AuditOutcome), name="ck_audit_events_outcome"),
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_actor", "actor_type", "actor_id"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_audit_events_outcome", "outcome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    def __repr__(self) -> str:
        # Never include the summary: it is sanitized, but logs are not the place for it.
        return (
            f"<AuditEvent(action={self.action!r}, outcome={self.outcome!r}, "
            f"actor_type={self.actor_type!r}, resource_type={self.resource_type!r})>"
        )
