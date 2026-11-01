# ruff: noqa: TC001, TC003
from __future__ import annotations

import enum
import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from cti.models.ai import AiProvider


class ModelSource(enum.StrEnum):
    LIVE = "live"
    CACHE = "cache"
    FALLBACK = "fallback"


class AiErrorCategory(enum.StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    INSUFFICIENT_QUOTA = "insufficient_quota"
    MODEL_UNAVAILABLE = "model_unavailable"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    PROVIDER_ERROR = "provider_error"
    NOT_CONFIGURED = "not_configured"


class AiModel(BaseModel):
    id: str
    name: str
    context_length: int | None = None


class AiError(BaseModel):
    category: AiErrorCategory
    message: str


class AiProviderStatus(BaseModel):
    provider: AiProvider
    display_name: str
    configured: bool
    key_hint: str | None
    models_fetched_at: datetime | None
    last_check_status: Literal["ok", "error"] | None
    last_check_category: AiErrorCategory | None
    last_checked_at: datetime | None
    setup_url: str


class AiDefault(BaseModel):
    provider: AiProvider
    model: str
    is_custom: bool


class AiSettings(BaseModel):
    providers: list[AiProviderStatus]
    default: AiDefault | None


class AiModelList(BaseModel):
    provider: AiProvider
    source: ModelSource
    fetched_at: datetime | None
    models: list[AiModel]
    error: AiError | None


class AiCheckResult(BaseModel):
    ok: bool
    error: AiError | None
    checked_at: datetime


class AiInferenceResult(BaseModel):
    ok: bool
    error: AiError | None
    latency_ms: int | None


class AiProviderKeyUpdate(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)

    @field_validator("api_key", mode="before")
    @classmethod
    def strip_and_validate_key(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("API key must not be empty")
        return value


def _validate_model_id(value: str) -> str:
    if not value.strip():
        raise ValueError("Model ID must not be empty or whitespace-only")
    if len(value) > 255:
        raise ValueError("Model ID must be at most 255 characters")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("Model ID must not contain control characters")
    return value


class AiDefaultUpdate(BaseModel):
    provider: AiProvider
    model: str
    is_custom: bool

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return _validate_model_id(value)


class AiInferenceTestRequest(BaseModel):
    model: str
    confirm: Literal[True]

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        return _validate_model_id(value)

    @field_validator("confirm", mode="before")
    @classmethod
    def validate_confirmation(cls, value: object) -> object:
        if value is not True:
            raise ValueError("Explicit confirmation is required")
        return value
