import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(max_length=128)
    description: str | None = None


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    description: str | None

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(ApiKeyResponse):
    key: str  # Full key, only shown at creation time
