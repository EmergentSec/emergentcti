"""Pydantic schemas for user management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cti.models.user import UserRole

# Top ~100 most common passwords — case-insensitive check at creation/change time.
_BLOCKED_PASSWORDS: frozenset[str] = frozenset({
    "password", "12345678", "123456789", "1234567890", "qwerty12",
    "qwerty123", "password1", "iloveyou", "sunshine1", "princess1",
    "football1", "charlie1", "access14", "master12", "dragon12",
    "monkey123", "letmein1", "abc12345", "trustno1", "baseball1",
    "starwars1", "shadow12", "ashley12", "michael1", "passw0rd",
    "11111111", "00000000", "12341234", "admin123", "welcome1",
    "monkey12", "dragon123", "login123", "qwerty1234", "solo1234",
    "1q2w3e4r", "master123", "changeme", "abcdefgh", "abcd1234",
    "superman", "jordan23", "harley12", "ranger12", "daniel12",
    "chelsea1", "password123", "hunter12", "buster12", "soccer12",
    "batman12", "trustno12", "thomas12", "robert12", "george12",
    "whatever", "qazwsx12", "zaq12wsx", "summer12", "winter12",
    "secret12", "computer", "internet", "explorer", "jennifer",
    "samantha", "michelle", "sunshine", "princess", "football",
    "baseball", "password12", "welcome12", "hello123", "charlie",
    "donald12", "jessica1", "pepper12", "ginger12", "letmein12",
    "mustang1", "shadow123", "ashley123", "michael12", "access123",
    "thunder1", "matrix12", "freedom1", "corvette", "maverick",
    "bluefish", "midnight", "cocacola", "mountain", "steelers",
    "dolphins", "cowboys1", "redskins", "packers1", "yankees1",
    "p@ssw0rd", "p@ssword", "pa$$word", "passw0rd1", "qwer1234",
    "asdf1234", "zxcv1234", "1234qwer", "1234asdf",
})


def _check_common_password(v: str) -> str:
    if v.lower() in _BLOCKED_PASSWORDS:
        raise ValueError("This password is too common — choose a stronger password")
    return v


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.user
    email: str | None = None

    @field_validator("password")
    @classmethod
    def password_not_common(cls, v: str) -> str:
        return _check_common_password(v)


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
    new_password: str = Field(min_length=8, max_length=128)
    current_password: str | None = None  # required for non-admin self-change

    @field_validator("new_password")
    @classmethod
    def new_password_not_common(cls, v: str) -> str:
        return _check_common_password(v)
