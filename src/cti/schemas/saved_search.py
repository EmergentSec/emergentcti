import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SavedSearchFilters(BaseModel):
    """The filter parameters that can be saved."""

    type: str | None = None
    value: str | None = None
    confidence_min: int | None = None
    tlp: str | None = None
    feed_id: str | None = None
    category: str | None = None
    tag: str | None = None


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    filters: SavedSearchFilters
    is_shared: bool = False


class SavedSearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    filters: SavedSearchFilters | None = None
    is_shared: bool | None = None


class SavedSearchOwner(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str


class SavedSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    filters: dict
    is_default: bool
    is_shared: bool
    user_id: uuid.UUID
    user: SavedSearchOwner | None = None
    created_at: datetime
    updated_at: datetime
