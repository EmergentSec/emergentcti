import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from cti.models.user import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.readonly


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    has_api_key: bool = False
    auth_provider: str = "local"
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def set_has_api_key(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["has_api_key"] = bool(data.get("api_key"))
        elif hasattr(data, "api_key"):
            # ORM object: wrap in a dict so Pydantic can pick up the computed field
            auth_provider = "local"
            if hasattr(data, "auth_provider") and data.auth_provider is not None:
                auth_provider = (
                    data.auth_provider.value
                    if hasattr(data.auth_provider, "value")
                    else str(data.auth_provider)
                )
            return {
                "id": data.id,
                "username": data.username,
                "email": data.email,
                "role": data.role,
                "is_active": data.is_active,
                "has_api_key": data.api_key is not None,
                "auth_provider": auth_provider,
                "created_at": data.created_at,
            }
        return data


class ApiKeyResponse(BaseModel):
    api_key: str
