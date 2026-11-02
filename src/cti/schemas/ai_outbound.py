"""Schemas for previewing content before it is sent to an external AI."""
# Pydantic resolves these annotations at runtime.
# ruff: noqa: TC001, TC003

from __future__ import annotations

import unicodedata
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from cti.models.ai import AiProvider
from cti.models.tlp import Tlp
from cti.services.ai.outbound_types import OutboundItemType


class OutboundRefInput(BaseModel):
    type: OutboundItemType
    id: uuid.UUID


class OutboundPreviewRequest(BaseModel):
    provider: AiProvider
    model: str = Field(min_length=1, max_length=255)
    refs: list[OutboundRefInput] = Field(max_length=25)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Model ID must not be empty or whitespace-only")
        if any(unicodedata.category(character) == "Cc" for character in value):
            raise ValueError("Model ID must not contain control characters")
        return value


class OutboundPreviewItem(BaseModel):
    type: OutboundItemType
    id: str
    label: str
    tlp: Tlp | None
    included: bool
    excluded_reason: Literal["tlp_restricted", "not_found", "not_visible"] | None
    redactions: int


class OutboundPreview(BaseModel):
    provider: AiProvider
    model: str
    destination_note: str
    items: list[OutboundPreviewItem]
    content: str
    content_chars: int
    digest: str
    expires_at: datetime
