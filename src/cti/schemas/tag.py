import uuid

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    # Normalized (and validated) by the service; this only bounds the raw input.
    name: str = Field(..., max_length=200)


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str


class TagWithCounts(TagResponse):
    observable_count: int
    report_count: int
