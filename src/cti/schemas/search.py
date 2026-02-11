from datetime import datetime

from pydantic import BaseModel, Field

from cti.models.observable import ObservableType


class SearchRequest(BaseModel):
    q: str = Field(min_length=1)
    type: ObservableType | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    confidence_min: int | None = Field(default=None, ge=0, le=100)
    confidence_max: int | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class SearchHit(BaseModel):
    id: str
    type: str
    value: str
    confidence_score: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    tlp: str | None = None
    tags: list[str] = Field(default_factory=list)
    score: float
    highlights: dict[str, list[str]] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    total: int
    page: int
    size: int
