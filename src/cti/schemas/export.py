import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from cti.models.export_profile import ExportFormat
from cti.models.observable import ObservableType


class ExportObservable(BaseModel):
    type: ObservableType
    value: str
    confidence_score: int
    last_seen: datetime | None
    sources: list[str]  # Feed names


class JsonExportResponse(BaseModel):
    exported_at: datetime
    count: int
    filters: dict
    observables: list[ExportObservable]

# Upper bound for age filters: keeps cutoff arithmetic far from datetime overflow.
MAX_AGE_DAYS_LIMIT = 36500


def _clean_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Name is required")
    return v


def _clean_description(v: str | None) -> str | None:
    if v is None:
        return None
    return v.strip() or None


class ExportProfileCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(default=None, max_length=500)
    format: ExportFormat
    type: ObservableType | None = None
    confidence_min: int = Field(default=70, ge=0, le=100)
    max_age_days: int | None = Field(default=None, ge=1, le=MAX_AGE_DAYS_LIMIT)
    feed_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        return _clean_description(v)


class ExportProfileUpdate(BaseModel):
    """PUT body. Omitted fields are left unchanged; explicit nulls clear nullable filters."""

    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    format: ExportFormat | None = None
    type: ObservableType | None = None
    confidence_min: int | None = Field(default=None, ge=0, le=100)
    max_age_days: int | None = Field(default=None, ge=1, le=MAX_AGE_DAYS_LIMIT)
    feed_id: uuid.UUID | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("Name is required")
        return _clean_name(v)

    @field_validator("description")
    @classmethod
    def _description(cls, v: str | None) -> str | None:
        return _clean_description(v)

    @field_validator("format", "confidence_min")
    @classmethod
    def _not_null(cls, v: object) -> object:
        if v is None:
            raise ValueError("Field cannot be null")
        return v


class ExportProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    format: ExportFormat
    type: ObservableType | None
    confidence_min: int
    max_age_days: int | None
    feed_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExportProfilePreview(BaseModel):
    count: int
    excluded_allowlisted: int
    sample: list[str]
