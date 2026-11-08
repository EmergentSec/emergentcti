"""Unit tests for threat-intel skills and prompt builders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cti.services.threat_intel import pipeline
from cti.services.threat_intel.feed_aggregator import FeedAggregator, FeedAggregatorError


def test_list_skills_includes_core_package() -> None:
    ids = {skill["id"] for skill in pipeline.list_skills()}
    assert ids == {"feed_aggregator", "threat_researcher", "threat_report_writer"}


def test_skills_have_no_anna_branding() -> None:
    for skill in pipeline.list_skills():
        body = pipeline.load_skill(skill["id"]).casefold()
        assert "anna" not in body
        assert "ostra" not in body


def test_load_skill_rejects_path_escape() -> None:
    with pytest.raises(pipeline.ThreatIntelError) as exc:
        pipeline.load_skill("../secrets")
    assert exc.value.status_code == 404


def test_build_prompts_embed_item() -> None:
    item = {
        "title": "CVE-2026-12345 Example",
        "cve_id": "CVE-2026-12345",
        "link": "https://nvd.nist.gov/vuln/detail/CVE-2026-12345",
        "severity": "CRITICAL",
    }
    research = pipeline.build_research_prompt(item, today="2026-11-08")
    assert "CVE-2026-12345" in research
    assert "Threat Researcher" in research
    writer = pipeline.build_writer_prompt(item, "Summary: test", today="2026-11-08")
    assert "Threat Report Writer" in writer
    assert "Summary: test" in writer
    assert "homelab" in writer


def test_title_and_footer_helpers() -> None:
    body = "# CVE-2026-1 — Title\n\n## Executive Summary\n\nHello world.\n\n## Next\n\nx\n"
    assert pipeline._title_from_markdown(body, "fallback") == "CVE-2026-1 — Title"  # noqa: SLF001
    assert pipeline._summary_from_markdown(body) == "Hello world."  # noqa: SLF001
    with_footer = body + "\nMISTAKES: none\nFRICTION: none\nWISHES: none\n"
    cleaned = pipeline._strip_telemetry_footer(with_footer)  # noqa: SLF001
    assert "MISTAKES" not in cleaned


def test_feed_aggregator_missing_config(tmp_path: Path) -> None:
    with pytest.raises(FeedAggregatorError):
        FeedAggregator(str(tmp_path / "missing.json"))


def test_feed_aggregator_loads_example_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    example = Path(__file__).resolve().parents[2] / "src/cti/services/threat_intel/config.example.json"
    config_path = tmp_path / "config.json"
    config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("NVD_API_KEY", "env-test-key")
    aggregator = FeedAggregator(str(config_path))
    assert aggregator.config["nvd"]["api_key"] == "env-test-key"
    assert "US-CERT CISA" in {feed["name"] for feed in aggregator.config["rss_feeds"]}


def test_fetch_feeds_with_empty_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = {
        "log_file": str(tmp_path / "feed.log"),
        "log_level": "ERROR",
        "state_file": str(tmp_path / "state.json"),
        "rss_feeds": [],
        "nvd": {"enabled": False},
        "vendors": [],
        "filters": {"keywords": [], "severity": [], "products": []},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = pipeline.fetch_feeds(config_path=str(config_path), data_dir=str(tmp_path / "data"))
    assert result.total_items == 0
    assert result.items == []
