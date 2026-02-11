import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cti.models.relationship import RelationshipType


class ObservableSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    value: str
    confidence_score: int


class RelationshipCreate(BaseModel):
    target_id: uuid.UUID
    relationship_type: str
    confidence: int = Field(default=50, ge=0, le=100)
    metadata: dict | None = None

    @model_validator(mode="after")
    def validate_type(self) -> "RelationshipCreate":
        valid = {e.value for e in RelationshipType}
        if self.relationship_type not in valid:
            raise ValueError(
                f"Invalid relationship type. Must be one of: {sorted(valid)}"
            )
        return self


class RelationshipUpdate(BaseModel):
    relationship_type: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    metadata: dict | None = None

    @model_validator(mode="after")
    def validate_type(self) -> "RelationshipUpdate":
        if self.relationship_type is not None:
            valid = {e.value for e in RelationshipType}
            if self.relationship_type not in valid:
                raise ValueError(
                    f"Invalid relationship type. Must be one of: {sorted(valid)}"
                )
        return self


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    relationship_type: str
    confidence: int
    metadata: dict | None = None
    created_at: datetime
    created_by: uuid.UUID | None = None
    source: ObservableSummary | None = None
    target: ObservableSummary | None = None

    @model_validator(mode="before")
    @classmethod
    def map_metadata_field(cls, data: object) -> object:
        """Map ORM metadata_ attribute to schema metadata field."""
        if hasattr(data, "metadata_"):
            # ORM object: copy metadata_ to a dict so Pydantic sees 'metadata'
            d = {
                "id": data.id,
                "source_id": data.source_id,
                "target_id": data.target_id,
                "relationship_type": data.relationship_type,
                "confidence": data.confidence,
                "metadata": data.metadata_,
                "created_at": data.created_at,
                "created_by": data.created_by,
                "source": data.source if hasattr(data, "source") else None,
                "target": data.target if hasattr(data, "target") else None,
            }
            return d
        return data


class GraphNode(BaseModel):
    id: str
    type: str
    value: str
    confidence_score: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence: int


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
