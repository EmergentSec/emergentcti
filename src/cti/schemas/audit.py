"""Audit history response schemas (read-only; there are no write schemas)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from cti.models.audit import ActorType, AuditOutcome


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_at: datetime
    actor_type: ActorType
    actor_id: str | None
    actor_label: str | None
    action: str
    resource_type: str
    resource_id: str | None
    resource_label: str | None
    outcome: AuditOutcome
    summary: dict[str, Any]

    @field_validator("occurred_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        # SQLite returns naive values; every stored timestamp is UTC.
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class AuditEventPage(BaseModel):
    items: list[AuditEventResponse]
    total: int
    page: int
    size: int
    pages: int


class AuditMetaResponse(BaseModel):
    actions: list[str]
    actor_types: list[str]
    outcomes: list[str]
    resource_types: list[str]
    retention_days: int
