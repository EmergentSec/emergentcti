import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, Field, StringConstraints

from cti.models.observable import ObservableType
from cti.models.tlp import Tlp

# Reasons are trimmed; 1-500 characters remain.
TlpReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ObservableCreate(BaseModel):
    type: ObservableType
    value: str = Field(..., min_length=1, max_length=2048)
    confidence_score: int = Field(default=75, ge=0, le=100)
    # Manual marking (#15). ``tlp`` is canonical; ``manual_tlp`` is accepted too.
    tlp: Tlp | None = Field(default=None, validation_alias=AliasChoices("tlp", "manual_tlp"))


class TlpOverrideRequest(BaseModel):
    # Required and never null: an override is always one of the five markings.
    tlp: Tlp
    reason: TlpReason


class TlpOverrideResponse(BaseModel):
    tlp: Tlp
    reason: str
    set_at: datetime
    set_by: str | None


class TlpSource(BaseModel):
    kind: Literal["feed", "report", "manual"]
    id: uuid.UUID | None
    name: str
    tlp: Tlp | None


class TagsUpdate(BaseModel):
    tags: list[Annotated[str, StringConstraints(max_length=200)]] = Field(max_length=100)


class ObservableSourceResponse(BaseModel):
    feed_id: uuid.UUID
    feed_name: str
    source_confidence: int
    native_confidence: int
    first_seen_by_feed: datetime
    last_seen_by_feed: datetime

    model_config = {"from_attributes": True}


class ConfidenceOverrideRequest(BaseModel):
    confidence: int = Field(strict=True, ge=0, le=100)


class ConfidenceOverrideResponse(BaseModel):
    value: int
    set_at: datetime
    set_by: str | None


class ObservableResponse(BaseModel):
    id: uuid.UUID
    type: ObservableType
    value: str
    confidence_score: int
    manual_confidence: int | None
    confidence_override: ConfidenceOverrideResponse | None
    first_seen: datetime | None
    last_seen: datetime | None
    source_count: int = 0
    sources: list[ObservableSourceResponse] = []
    # Derived at read time from the current allowlist; never persisted.
    allowlisted: bool = False
    allowlist_entry_ids: list[uuid.UUID] = []
    # TLP and tags (#15). effective_tlp is derived at read time; null = Unspecified.
    tags: list[str] = []
    manual_tlp: Tlp | None = None
    effective_tlp: Tlp | None = None
    tlp_sources: list[TlpSource] = []
    tlp_override: TlpOverrideResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ObservableListResponse(BaseModel):
    items: list[ObservableResponse]
    total: int
    page: int
    size: int
    pages: int
