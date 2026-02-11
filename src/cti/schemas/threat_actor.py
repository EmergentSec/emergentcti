import math
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ThreatActorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    aliases: list[str] | None = None
    description: str | None = None
    motivation: str | None = None
    sophistication: str | None = None
    country: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    tlp: str = "clear"
    external_references: list[dict] | None = None


class ThreatActorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    aliases: list[str] | None = None
    description: str | None = None
    motivation: str | None = None
    sophistication: str | None = None
    country: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    tlp: str | None = None
    external_references: list[dict] | None = None


class ObservableLink(BaseModel):
    observable_id: uuid.UUID


class TechniqueLink(BaseModel):
    technique_id: uuid.UUID


class ThreatActorObservableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    value: str


class ThreatActorTechniqueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    external_id: str
    name: str


class ThreatActorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    aliases: list[str] | None
    description: str | None
    motivation: str | None
    sophistication: str | None
    country: str | None
    first_seen: datetime | None
    last_seen: datetime | None
    tlp: str
    external_references: list[dict] | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    observables: list[ThreatActorObservableResponse]
    techniques: list[ThreatActorTechniqueResponse]

    @field_validator("observables", mode="before")
    @classmethod
    def flatten_observables(cls, v: list) -> list:
        if not v:
            return []
        result = []
        for item in v:
            if hasattr(item, "id"):
                result.append(
                    ThreatActorObservableResponse(
                        id=item.id,
                        type=item.type.value if hasattr(item.type, "value") else str(item.type),
                        value=item.value,
                    )
                )
            elif isinstance(item, dict):
                result.append(ThreatActorObservableResponse(**item))
            else:
                result.append(item)
        return result

    @field_validator("techniques", mode="before")
    @classmethod
    def flatten_techniques(cls, v: list) -> list:
        if not v:
            return []
        result = []
        for item in v:
            if hasattr(item, "id"):
                result.append(
                    ThreatActorTechniqueResponse(
                        id=item.id,
                        external_id=item.external_id,
                        name=item.name,
                    )
                )
            elif isinstance(item, dict):
                result.append(ThreatActorTechniqueResponse(**item))
            else:
                result.append(item)
        return result


class ThreatActorListResponse(BaseModel):
    items: list[ThreatActorResponse]
    total: int
    page: int
    size: int
    pages: int = 0

    @model_validator(mode="after")
    def compute_pages(self) -> "ThreatActorListResponse":
        if self.size > 0:
            self.pages = math.ceil(self.total / self.size)
        return self
