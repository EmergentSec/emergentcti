"""API schemas for the threat-intel pipeline."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ThreatIntelSkill(BaseModel):
    id: str
    title: str
    path: str


class ThreatIntelSkillBody(BaseModel):
    id: str
    title: str
    content: str


class FeedFetchResponse(BaseModel):
    timestamp: str
    total_items: int
    summary: dict[str, Any]
    items: list[dict[str, Any]]
    state_file: str
    config_path: str


class GenerateReportRequest(BaseModel):
    """Generate a deep-dive report for one feed item via research + writer models."""

    item: dict[str, Any] = Field(
        description="A single feed item (title, link, source, severity, cve_id, …)."
    )
    environment: Literal["homelab"] = "homelab"


class GenerateReportResponse(BaseModel):
    report_id: str
    title: str
    research_provider: str
    research_model: str
    writer_provider: str
    writer_model: str
    research_chars: int
    report_chars: int
