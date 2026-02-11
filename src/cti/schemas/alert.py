import math
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Alert Rule schemas
# ---------------------------------------------------------------------------


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    enabled: bool = True
    match_type: str | None = None
    match_value_pattern: str | None = None
    match_tags: list[str] | None = None
    match_tlp: str | None = None
    match_confidence_min: int | None = Field(default=None, ge=0, le=100)
    match_feed_id: uuid.UUID | None = None
    notification_channels: list[dict] = Field(default_factory=list)
    cooldown_minutes: int = Field(default=60, ge=0)


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    enabled: bool | None = None
    match_type: str | None = None
    match_value_pattern: str | None = None
    match_tags: list[str] | None = None
    match_tlp: str | None = None
    match_confidence_min: int | None = Field(default=None, ge=0, le=100)
    match_feed_id: uuid.UUID | None = None
    notification_channels: list[dict] | None = None
    cooldown_minutes: int | None = Field(default=None, ge=0)


class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    enabled: bool
    created_by: uuid.UUID | None
    match_type: str | None
    match_value_pattern: str | None
    match_tags: list[str] | None
    match_tlp: str | None
    match_confidence_min: int | None
    match_feed_id: uuid.UUID | None
    notification_channels: list[dict]
    cooldown_minutes: int
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Alert Event schemas
# ---------------------------------------------------------------------------


class AlertEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    observable_id: uuid.UUID
    triggered_at: datetime
    notification_sent: bool
    notification_error: str | None
    rule_name: str | None = None
    observable_value: str | None = None


class AlertEventListResponse(BaseModel):
    items: list[AlertEventResponse]
    total: int
    page: int
    size: int
    pages: int = 0

    @model_validator(mode="after")
    def compute_pages(self) -> "AlertEventListResponse":
        if self.size > 0:
            self.pages = math.ceil(self.total / self.size)
        return self


# ---------------------------------------------------------------------------
# Webhook Config schemas
# ---------------------------------------------------------------------------

VALID_WEBHOOK_EVENTS = [
    "observable.created",
    "alert.triggered",
    "feed.completed",
    "enrichment.completed",
]


class WebhookConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    url: str = Field(min_length=1, max_length=2048)
    secret: str | None = None
    enabled: bool = True
    events: list[str] = Field(default_factory=list)


class WebhookConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    secret: str | None = None
    enabled: bool | None = None
    events: list[str] | None = None


class WebhookConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    has_secret: bool = False
    enabled: bool
    events: list[str]
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def compute_has_secret(cls, data: Any) -> Any:
        if hasattr(data, "__dict__"):
            # ORM model instance
            return {
                "id": data.id,
                "name": data.name,
                "url": data.url,
                "has_secret": data.secret_encrypted is not None,
                "enabled": data.enabled,
                "events": data.events,
                "created_by": data.created_by,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        # dict
        result = dict(data)
        result["has_secret"] = data.get("secret_encrypted") is not None
        return result


class WebhookTestResponse(BaseModel):
    success: bool
    status_code: int | None = None
    error: str | None = None
