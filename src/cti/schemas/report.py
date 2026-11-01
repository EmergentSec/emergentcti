# Pydantic resolves these annotations at runtime.
# ruff: noqa: TC001, TC003
from __future__ import annotations

import unicodedata
import uuid
from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from cti.models.observable import ObservableType
from cti.models.report import ContentFormat, ReportOrigin
from cti.models.tlp import Tlp

# Required when a feed/report marking is loosened (#15); trimmed, 1-500 chars.
TlpChangeReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]

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
    tlp: Tlp | None = None

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
    # Explicit null = Unspecified. Loosening needs tlp_change_reason.
    tlp: Tlp | None = None
    tlp_change_reason: TlpChangeReason | None = None

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
    tlp: Tlp | None = None
    tags: list[str] = []
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
    tags: list[str] = []
    tlp: list[str] = []
    page: int = Field(default=1, ge=1)
    size: int = Field(default=25, ge=1, le=100)


# ── IOC extraction and reviewed import (#14) ─────────────────────────────

CandidateType = Literal["ip-addr", "domain-name", "url", "file-hash", "email-addr"]
CandidateStatus = Literal["new", "existing", "invalid"]
SourceStatus = Literal["extracted", "empty", "unsupported"]

MAX_IMPORT_ITEMS = 1000


class ExtractionSource(BaseModel):
    kind: Literal["content", "attachment"]
    filename: str | None
    content_type: str | None
    status: SourceStatus
    reason: str | None


class ExtractionCandidate(BaseModel):
    type: CandidateType
    value: str
    original: str
    context: str
    occurrences: int
    defanged: bool
    status: CandidateStatus
    existing_observable_id: uuid.UUID | None
    existing_confidence: int | None
    already_attributed: bool
    allowlisted: bool
    allowlist_matches: list[str]
    warnings: list[str]


class ExtractionCounts(BaseModel):
    total: int
    new: int
    existing: int
    invalid: int


class ExtractionPreview(BaseModel):
    report_id: uuid.UUID
    sources: list[ExtractionSource]
    candidates: list[ExtractionCandidate]
    truncated: bool
    counts: ExtractionCounts


class ImportItem(BaseModel):
    # Free-form on purpose: anything that is not a server-side candidate is
    # rejected by the service with the not_a_candidate code.
    type: str = Field(max_length=32)
    value: str = Field(max_length=8192)


class ImportRequest(BaseModel):
    confidence: int = Field(strict=True, ge=0, le=100)
    items: list[ImportItem] = Field(min_length=1, max_length=MAX_IMPORT_ITEMS)

    @field_validator("items")
    @classmethod
    def items_are_unique(cls, items: list[ImportItem]) -> list[ImportItem]:
        seen: set[tuple[str, str]] = set()
        duplicates: list[str] = []
        for item in items:
            key = (item.type, item.value)
            if key in seen:
                duplicates.append(f"{item.type} {item.value}")
            seen.add(key)
        if duplicates:
            raise PydanticCustomError(
                "duplicate_items",
                "Duplicate items: {duplicates}",
                {"duplicates": ", ".join(duplicates[:20])},
            )
        return items


class ImportedObservable(BaseModel):
    id: uuid.UUID
    type: CandidateType
    value: str
    confidence_score: int
    created: bool


class ImportResult(BaseModel):
    created: int
    attributed_existing: int
    already_attributed: int
    observables: list[ImportedObservable]
