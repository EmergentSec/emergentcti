"""Pydantic schemas for user management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from cti.models.user import UserRole


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8)
    role: UserRole = UserRole.user
    email: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    email: str | None = None


class PasswordChange(BaseModel):
    new_password: str = Field(min_length=8)
    current_password: str | None = None  # required for non-admin self-change
