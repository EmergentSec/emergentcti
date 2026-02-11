"""Confidence score computation from enrichment provider results."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.observable import Observable

logger = logging.getLogger(__name__)

# Provider-specific score extractors
_EXTRACTORS: dict[str, "type[object]"] = {}


def compute_provider_confidence(provider_name: str, result_data: dict) -> int | None:
    """Extract a 0-100 confidence score from a provider's enrichment result.

    Returns None if the provider result doesn't contain usable score data.
    """
    if not result_data:
        return None

    if provider_name == "abuseipdb":
        score = result_data.get("abuseConfidenceScore")
        if score is not None:
            return max(0, min(100, int(score)))

    elif provider_name == "virustotal":
        stats = result_data.get("last_analysis_stats")
        if stats and isinstance(stats, dict):
            malicious = stats.get("malicious", 0)
            total = sum(stats.values())
            if total > 0:
                return max(0, min(100, int((malicious / total) * 100)))

    elif provider_name == "urlscan":
        score = result_data.get("score")
        if score is not None:
            return max(0, min(100, int(score)))
        if result_data.get("malicious"):
            return 85

    elif provider_name == "greynoise":
        classification = result_data.get("classification", "").lower()
        return {"malicious": 85, "benign": 15, "unknown": 50}.get(classification)

    elif provider_name == "shodan":
        vulns = result_data.get("vulns", [])
        if isinstance(vulns, list):
            return max(0, min(100, 50 + len(vulns) * 10))

    return None


async def update_observable_confidence(
    db: AsyncSession,
    observable_id: uuid.UUID,
    provider_score: int,
) -> None:
    """Update observable confidence using weighted average of current and provider score.

    Weight: 0.6 for enrichment provider, 0.4 for existing score.
    """
    result = await db.execute(
        select(Observable.confidence_score).where(Observable.id == observable_id)
    )
    current = result.scalar_one_or_none()
    if current is None:
        return

    new_score = int(current * 0.4 + provider_score * 0.6)
    new_score = max(0, min(100, new_score))

    await db.execute(
        update(Observable)
        .where(Observable.id == observable_id)
        .values(confidence_score=new_score, updated_at=datetime.now(UTC))
    )
    logger.debug(
        "Updated confidence for %s: %d -> %d (provider=%d)",
        observable_id,
        current,
        new_score,
        provider_score,
    )
