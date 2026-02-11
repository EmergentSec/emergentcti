import uuid

from pydantic import BaseModel, Field


class BulkObservableUpdate(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    tlp: str | None = None
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None = None       # replaces tags
    add_tags: list[str] | None = None   # appends tags
    category: str | None = None


class BulkIds(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class BulkFeedUpdate(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    enabled: bool | None = None


class BulkUserUpdate(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    is_active: bool | None = None
    role: str | None = None


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
