"""Orchestrate feed fetch → research model → writer model → Report.

Public feed content and skill prompts are approved for the gateway as
:class:`ApprovedOutbound` with empty item refs (no instance CTI objects).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cti.models.ai_usage import AiAction
from cti.models.report import ContentFormat, ReportOrigin
from cti.schemas.ai import AiModelRole
from cti.schemas.report import ReportCreate
from cti.services import ai_settings_service, report_service
from cti.services.ai import gateway
from cti.services.ai.outbound_types import ApprovedOutbound
from cti.services.threat_intel.feed_aggregator import FeedAggregator

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from cti.services.audit import Actor

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _PACKAGE_DIR / "skills"
_DEFAULT_DATA_DIR = Path("data/threat_intel")
_FOOTER_RE = re.compile(
    r"\nMISTAKES:.*?\nFRICTION:.*?\nWISHES:.*?\s*\Z",
    re.DOTALL | re.IGNORECASE,
)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class FeedFetchResult:
    timestamp: str
    total_items: int
    summary: dict[str, Any]
    items: list[dict[str, Any]]
    state_file: str
    config_path: str


@dataclass(frozen=True, slots=True)
class GenerateReportResult:
    report_id: str
    title: str
    research_provider: str
    research_model: str
    writer_provider: str
    writer_model: str
    research_chars: int
    report_chars: int


class ThreatIntelError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def list_skills() -> list[dict[str, str]]:
    skills = []
    for path in sorted(_SKILLS_DIR.glob("*.md")):
        skills.append({"id": path.stem, "path": str(path), "title": _skill_title(path)})
    return skills


def load_skill(skill_id: str) -> str:
    path = _SKILLS_DIR / f"{skill_id}.md"
    if not path.is_file() or path.resolve().parent != _SKILLS_DIR.resolve():
        raise ThreatIntelError(404, f"Unknown skill: {skill_id}")
    return path.read_text(encoding="utf-8")


def _skill_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def resolve_paths(
    *,
    config_path: str | None = None,
    data_dir: str | None = None,
) -> tuple[Path, Path]:
    data = Path(data_dir) if data_dir else _DEFAULT_DATA_DIR
    data.mkdir(parents=True, exist_ok=True)
    config = Path(config_path) if config_path else data / "config.json"
    if not config.is_file():
        example = _PACKAGE_DIR / "config.example.json"
        if not config_path and example.is_file():
            config.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            raise ThreatIntelError(
                409,
                f"Threat-intel config not found at {config}. "
                "Copy config.example.json and set an NVD API key if desired.",
            )
    return config, data


def fetch_feeds(
    *,
    config_path: str | None = None,
    data_dir: str | None = None,
) -> FeedFetchResult:
    config, data = resolve_paths(config_path=config_path, data_dir=data_dir)
    # Keep state next to the config by default.
    aggregator = FeedAggregator(str(config))
    # Prefer writing state under the data dir when the config uses a relative path.
    state_name = Path(aggregator.state_file).name
    aggregator.state_file = data / state_name
    aggregator.state = aggregator._load_state()  # noqa: SLF001 — rebind after path change

    report = aggregator.aggregate()
    # Drop bulky raw blobs before returning to the API.
    items: list[dict[str, Any]] = []
    for item in report.get("items", []):
        cleaned = {k: v for k, v in item.items() if k != "raw"}
        items.append(cleaned)

    json_out = data / f"feed_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    aggregator.save_json_report(
        {**report, "items": items},
        str(json_out),
    )
    return FeedFetchResult(
        timestamp=str(report.get("timestamp", "")),
        total_items=int(report.get("total_items", 0)),
        summary=dict(report.get("summary") or {}),
        items=items,
        state_file=str(aggregator.state_file),
        config_path=str(config),
    )


def _approve(provider: Any, model: str, content: str) -> ApprovedOutbound:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ApprovedOutbound(
        provider=provider,
        model=model,
        digest=digest,
        content=content,
        item_refs=(),
    )


def _strip_telemetry_footer(text: str) -> str:
    return _FOOTER_RE.sub("", text).rstrip() + "\n"


def _title_from_markdown(content: str, fallback: str) -> str:
    match = _TITLE_RE.search(content)
    if match:
        return match.group(1).strip()[:500]
    return fallback[:500]


def _summary_from_markdown(content: str) -> str | None:
    marker = "## Executive Summary"
    if marker not in content:
        return None
    body = content.split(marker, 1)[1]
    next_heading = re.search(r"\n##\s+", body)
    section = body[: next_heading.start()] if next_heading else body
    text = re.sub(r"\s+", " ", section).strip()
    return text[:2000] if text else None


def build_research_prompt(item: dict[str, Any], *, today: str) -> str:
    skill = load_skill("threat_researcher")
    payload = json.dumps(item, indent=2, default=str)
    return (
        f"{skill}\n\n"
        f"Today's date (America/New_York context): {today}\n\n"
        "Investigate the following feed item. Return the output shape from the skill.\n\n"
        f"```json\n{payload}\n```\n"
    )


def build_writer_prompt(
    item: dict[str, Any],
    research: str,
    *,
    today: str,
    environment: str = "homelab",
) -> str:
    skill = load_skill("threat_report_writer")
    payload = json.dumps(item, indent=2, default=str)
    return (
        f"{skill}\n\n"
        f"Today's date: {today}\n"
        f"environment: {environment}\n\n"
        "feed_item:\n"
        f"```json\n{payload}\n```\n\n"
        "research:\n"
        f"```\n{research}\n```\n"
    )


async def generate_report_from_item(
    db: AsyncSession,
    *,
    actor: Actor,
    item: dict[str, Any],
    environment: str = "homelab",
    created_by_id: Any | None = None,
    db_factory: gateway.SessionContextFactory | None = None,
) -> GenerateReportResult:
    today = datetime.now(UTC).astimezone().strftime("%Y-%m-%d")
    research_sel = await ai_settings_service.get_role_selection(db, AiModelRole.RESEARCH)
    writer_sel = await ai_settings_service.get_role_selection(db, AiModelRole.WRITER)

    research_prompt = build_research_prompt(item, today=today)
    research_outcome = await gateway.run_inference(
        db_factory or gateway.independent_session,
        actor=actor,
        action=AiAction.THREAT_RESEARCH,
        provider=research_sel.provider,
        model=research_sel.model,
        prompt=research_prompt,
        approved=_approve(research_sel.provider, research_sel.model, research_prompt),
        retry_of=None,
    )
    if not research_outcome.ok or not research_outcome.text:
        message = (
            research_outcome.error.message
            if research_outcome.error is not None
            else "Research model returned no text"
        )
        raise ThreatIntelError(502, f"Threat research failed: {message}")

    research_text = _strip_telemetry_footer(research_outcome.text)
    writer_prompt = build_writer_prompt(
        item, research_text, today=today, environment=environment
    )
    writer_outcome = await gateway.run_inference(
        db_factory or gateway.independent_session,
        actor=actor,
        action=AiAction.REPORT_WRITE,
        provider=writer_sel.provider,
        model=writer_sel.model,
        prompt=writer_prompt,
        approved=_approve(writer_sel.provider, writer_sel.model, writer_prompt),
        retry_of=None,
    )
    if not writer_outcome.ok or not writer_outcome.text:
        message = (
            writer_outcome.error.message
            if writer_outcome.error is not None
            else "Writer model returned no text"
        )
        raise ThreatIntelError(502, f"Report writing failed: {message}")

    report_body = _strip_telemetry_footer(writer_outcome.text)
    fallback_title = str(item.get("title") or item.get("cve_id") or "Threat intel report")
    title = _title_from_markdown(report_body, fallback_title)
    now = datetime.now(UTC).replace(tzinfo=None)
    create = ReportCreate(
        title=title,
        origin=ReportOrigin.INTERNAL,
        source_name="Threat Intel Pipeline",
        published_at=now,
        summary=_summary_from_markdown(report_body),
        source_url=item.get("link") if isinstance(item.get("link"), str) else None,
        content=report_body,
        content_format=ContentFormat.MARKDOWN,
        is_ai_generated=True,
        ai_provider=writer_sel.provider.value,
        ai_model=writer_sel.model,
        ai_generated_at=now,
    )
    report = await report_service.create_report(db, create, created_by_id=created_by_id)
    return GenerateReportResult(
        report_id=str(report.id),
        title=report.title,
        research_provider=research_sel.provider.value,
        research_model=research_sel.model,
        writer_provider=writer_sel.provider.value,
        writer_model=writer_sel.model,
        research_chars=len(research_text),
        report_chars=len(report_body),
    )
