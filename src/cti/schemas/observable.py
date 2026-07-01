import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from cti.models.observable import ObservableType


class ObservableCreate(BaseModel):
    type: ObservableType
    value: str = Field(..., min_length=1, max_length=2048)
    confidence_score: int = Field(default=75, ge=0, le=100)


class ObservableSourceResponse(BaseModel):
    feed_id: uuid.UUID
    feed_name: str
    source_confidence: int
    native_confidence: int
    first_seen_by_feed: datetime
    last_seen_by_feed: datetime

    model_config = {"from_attributes": True}


class ObservableResponse(BaseModel):
    id: uuid.UUID
    type: ObservableType
    value: str
    confidence_score: int
    first_seen: datetime | None
    last_seen: datetime | None
    source_count: int = 0
    sources: list[ObservableSourceResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ObservableListResponse(BaseModel):
    items: list[ObservableResponse]
    total: int
    page: int
    size: int
    pages: int
