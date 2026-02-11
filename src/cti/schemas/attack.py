import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TacticResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str
    name: str
    description: str | None
    url: str | None
    order: int


class TechniqueBrief(BaseModel):
    """Lightweight version for lists and nested references."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str
    name: str
    is_subtechnique: bool


class TechniqueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str
    name: str
    description: str | None
    is_subtechnique: bool
    parent_id: uuid.UUID | None
    url: str | None
    tactics: list[TacticResponse] = []


class ObservableTechniqueCreate(BaseModel):
    technique_id: uuid.UUID


class ObservableTechniqueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    observable_id: uuid.UUID
    technique_id: uuid.UUID
    added_by: uuid.UUID | None
    created_at: datetime
    technique: TechniqueBrief | None = None


class HeatmapCell(BaseModel):
    tactic_id: str
    tactic_name: str
    technique_id: str
    technique_name: str
    count: int


class HeatmapResponse(BaseModel):
    tactics: list[TacticResponse]
    cells: list[HeatmapCell]
