import math
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: str | None
    user_id: uuid.UUID | None
    username: str | None = None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def extract_username(cls, data: Any) -> Any:
        if hasattr(data, "__dict__"):
            # ORM model instance
            username = None
            if data.user is not None:
                username = data.user.username
            return {
                "id": data.id,
                "action": data.action,
                "entity_type": data.entity_type,
                "entity_id": data.entity_id,
                "user_id": data.user_id,
                "username": username,
                "details": data.details,
                "ip_address": data.ip_address,
                "created_at": data.created_at,
            }
        return data


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    size: int
    pages: int = 0

    @model_validator(mode="after")
    def compute_pages(self) -> "AuditLogListResponse":
        if self.size > 0:
            self.pages = math.ceil(self.total / self.size)
        return self
