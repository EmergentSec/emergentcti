import uuid
from datetime import datetime

from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cti.models.feed import FeedRunStatus, FeedType


class FeedCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    feed_type: FeedType
    url: str | None = None
    config: dict | None = None
    schedule_cron: str | None = None
    enabled: bool = True
    auth_config: dict | None = None
    default_ttl_days: int | None = None

    @field_validator("schedule_cron")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")
        return v


class FeedUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    url: str | None = None
    config: dict | None = None
    schedule_cron: str | None = None
    enabled: bool | None = None
    auth_config: dict | None = None
    default_ttl_days: int | None = None

    @field_validator("schedule_cron")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")
        return v


class FeedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    feed_type: FeedType
    url: str | None
    config: dict | None
    schedule_cron: str | None
    enabled: bool
    default_ttl_days: int | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FeedRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    feed_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    status: FeedRunStatus
    observables_ingested: int
    error_message: str | None
