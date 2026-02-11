import math
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    threat_actor_id: uuid.UUID | None = None
    status: str = "suspected"
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    tlp: str = "clear"
    objective: str | None = None
    external_references: list[dict] | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    threat_actor_id: uuid.UUID | None = None
    status: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    tlp: str | None = None
    objective: str | None = None
    external_references: list[dict] | None = None


class CampaignObservableLink(BaseModel):
    observable_id: uuid.UUID


class CampaignObservableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    value: str


class CampaignThreatActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    threat_actor_id: uuid.UUID | None
    threat_actor: CampaignThreatActorResponse | None
    status: str
    first_seen: datetime | None
    last_seen: datetime | None
    tlp: str
    objective: str | None
    external_references: list[dict] | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    observables: list[CampaignObservableResponse]

    @field_validator("threat_actor", mode="before")
    @classmethod
    def flatten_threat_actor(cls, v: object) -> CampaignThreatActorResponse | None:
        if v is None:
            return None
        if hasattr(v, "id"):
            return CampaignThreatActorResponse(id=v.id, name=v.name)
        if isinstance(v, dict):
            return CampaignThreatActorResponse(**v)
        return v  # type: ignore[return-value]

    @field_validator("observables", mode="before")
    @classmethod
    def flatten_observables(cls, v: list) -> list:
        if not v:
            return []
        result = []
        for item in v:
            if hasattr(item, "id"):
                result.append(
                    CampaignObservableResponse(
                        id=item.id,
                        type=item.type.value if hasattr(item.type, "value") else str(item.type),
                        value=item.value,
                    )
                )
            elif isinstance(item, dict):
                result.append(CampaignObservableResponse(**item))
            else:
                result.append(item)
        return result


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int
    page: int
    size: int
    pages: int = 0

    @model_validator(mode="after")
    def compute_pages(self) -> "CampaignListResponse":
        if self.size > 0:
            self.pages = math.ceil(self.total / self.size)
        return self


class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    observable_id: uuid.UUID | None = None
    observable_value: str | None = None
    observable_type: str | None = None


class CampaignTimelineResponse(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    events: list[TimelineEvent]
