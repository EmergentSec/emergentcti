import uuid
from datetime import datetime

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from cti.models.feed import FeedRunStatus, FeedType
from cti.models.tlp import Tlp

TlpChangeReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]

_FEED_UPDATE_NON_NULLABLE = frozenset(
    {"name", "url", "feed_type", "enabled", "default_confidence", "config"}
)


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
    has_auth: bool = False
    auth_supported: bool = False
    auth_needs_repair: bool = False
    default_confidence: int
    tlp: Tlp | None = None
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
    tlp: Tlp | None = None


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
    # Explicit null = Unspecified. Loosening requires tlp_change_reason.
    tlp: Tlp | None = None
    tlp_change_reason: TlpChangeReason | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_on_non_nullable_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        for field in _FEED_UPDATE_NON_NULLABLE:
            if field in data and data[field] is None:
                raise ValueError(f"{field} cannot be null")
        return data

