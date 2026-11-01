# Pydantic resolves these annotations at runtime.
# ruff: noqa: TC001, TC003
from __future__ import annotations

import unicodedata
import uuid
from datetime import date, datetime
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from cti.models.observable import ObservableType
from cti.models.report import ContentFormat, ReportOrigin

TrimmedTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


def _validate_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    if any(
        character.isspace() or unicodedata.category(character) == "Cc"
        for character in value
    ):
        raise ValueError("source_url must not contain whitespace or control characters")
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url must be an http(s) URL")
    return value


def _has_ai_provenance(data: object) -> bool:
    return any(
        getattr(data, field) is not None
        for field in ("ai_provider", "ai_model", "ai_generated_at")
    )


class ReportCreate(BaseModel):
    title: TrimmedTitle
    origin: ReportOrigin
    source_name: str | None = Field(default=None, max_length=255)
    published_at: datetime | None = None
    summary: str | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    content: str | None = Field(default=None, max_length=1_000_000)
    content_format: ContentFormat = ContentFormat.MARKDOWN
    is_ai_generated: bool = False
    ai_provider: str | None = Field(default=None, max_length=255)
    ai_model: str | None = Field(default=None, max_length=255)
    ai_generated_at: datetime | None = None

    _source_url_is_http = field_validator("source_url")(_validate_source_url)

    @model_validator(mode="after")
    def validate_ai_provenance(self) -> ReportCreate:
        if not self.is_ai_generated and _has_ai_provenance(self):
            raise ValueError("ai_* fields require is_ai_generated=true")
        return self


class ReportUpdate(BaseModel):
    title: TrimmedTitle | None = None
    origin: ReportOrigin | None = None
    source_name: str | None = Field(default=None, max_length=255)
    published_at: datetime | None = None
    summary: str | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    content: str | None = Field(default=None, max_length=1_000_000)
    content_format: ContentFormat | None = None
    is_ai_generated: bool | None = None
    ai_provider: str | None = Field(default=None, max_length=255)
    ai_model: str | None = Field(default=None, max_length=255)
    ai_generated_at: datetime | None = None

    _source_url_is_http = field_validator("source_url")(_validate_source_url)

    @model_validator(mode="after")
    def validate_ai_provenance(self) -> ReportUpdate:
        for field in ("title", "origin", "content_format", "is_ai_generated"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        if self.is_ai_generated is False and _has_ai_provenance(self):
            raise ValueError("ai_* fields require is_ai_generated=true")
        return self


class ReportAttachment(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LinkedObservable(BaseModel):
    id: uuid.UUID
    type: ObservableType
    value: str
    confidence_score: int

    model_config = ConfigDict(from_attributes=True)


class ReportSummary(BaseModel):
    id: uuid.UUID
    title: str
    origin: ReportOrigin
    source_name: str | None
    published_at: datetime | None
    summary: str | None
    is_ai_generated: bool
    ai_provider: str | None
    ai_model: str | None
    has_attachment: bool
    created_at: datetime
    updated_at: datetime


class ReportDetail(ReportSummary):
    source_url: str | None
    content: str | None
    content_format: ContentFormat
    ai_generated_at: datetime | None
    created_by: str | None
    attachment: ReportAttachment | None
    observables: list[LinkedObservable]


class ReportListResponse(BaseModel):
    items: list[ReportSummary]
    total: int
    page: int
    size: int
    pages: int


class ReportObservableLink(BaseModel):
    observable_id: uuid.UUID


class ReportFilters(BaseModel):
    q: str | None = None
    origin: ReportOrigin | None = None
    source_name: str | None = None
    published_from: date | None = None
    published_to: date | None = None
    ai_generated: bool | None = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=25, ge=1, le=100)
