"""Pydantic schemas for auth endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str  # "admin" or "user"


class AuthMeResponse(BaseModel):
    type: str  # "user" or "api_key"
    id: uuid.UUID
    name: str   # username for users, key name for api_keys
    role: str   # "admin" or "user" for users; "admin" for api_keys (they get admin-level access)
