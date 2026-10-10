import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from cti.models.allowlist import AllowlistKind
from cti.models.observable import ObservableType


class AllowlistEntryCreate(BaseModel):
    kind: AllowlistKind
    value: str = Field(..., min_length=1, max_length=2048)
    # Required for ``exact``; implied (ip-addr / domain-name) for the other kinds.
    observable_type: ObservableType | None = None
    reason: str = Field(..., max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Reason is required")
        return v


class AllowlistEntryResponse(BaseModel):
    id: uuid.UUID
    kind: AllowlistKind
    value: str
    observable_type: ObservableType
    reason: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
