import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from cti.models.feed import FeedType, FeedRunStatus


class FeedRunResponse(BaseModel):
    id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    status: FeedRunStatus
    observables_ingested: int
    observables_new: int
    error_message: str | None

    model_config = {"from_attributes": True}


class FeedResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    feed_type: FeedType
    url: str | None
    config: dict | None
    schedule_cron: str | None
    enabled: bool
    is_preconfigured: bool
    default_confidence: int
    last_run_at: datetime | None
    observable_count: int = 0
    latest_run: FeedRunResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeedCreate(BaseModel):
    name: str = Field(max_length=256)
    description: str | None = None
    feed_type: FeedType
    url: str | None = None
    config: dict | None = None
    schedule_cron: str | None = None
    enabled: bool = True
    auth_config: dict | None = None  # Will be encrypted before storage
    default_confidence: int = Field(default=50, ge=0, le=100)


class FeedUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    feed_type: FeedType | None = None
    url: str | None = None
    config: dict | None = None
    schedule_cron: str | None = None
    enabled: bool | None = None
    auth_config: dict | None = None
    default_confidence: int | None = Field(default=None, ge=0, le=100)
