import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.campaign import Campaign
from cti.models.correlation import CorrelationEvent
from cti.models.enrichment import EnrichmentRun
from cti.models.observable import Observable
from cti.models.relationship import ObservableRelationship
from cti.models.report import Report
from cti.models.threat_actor import ThreatActor, threat_actor_observables

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "reports"
REPORTS_DIR = Path("/tmp/cti-reports")  # noqa: S108


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )


async def generate_report(db: AsyncSession, report_id: uuid.UUID) -> str:
    """Generate a report and return the file path."""
    report = await db.get(Report, report_id)
    if not report:
        raise ValueError(f"Report not found: {report_id}")

    # Mark as generating
    report.status = "generating"
    await db.flush()

    try:
        report_type = report.report_type
        parameters = report.parameters or {}

        if report_type == "threat_summary":
            context = await _gather_threat_summary(db, parameters)
        elif report_type == "observable_report":
            context = await _gather_observable_report(db, parameters)
        elif report_type == "campaign_brief":
            context = await _gather_campaign_brief(db, parameters)
        else:
            raise ValueError(f"Unknown report type: {report_type}")

        # Add common context
        context["report_title"] = report.title
        context["generated_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        context["report_type"] = report_type

        # Render template
        env = _get_jinja_env()
        template = env.get_template(f"{report_type}.html.j2")
        html_content = template.render(**context)

        # Ensure output directory exists
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path = REPORTS_DIR / f"{report_id}.html"
        file_path.write_text(html_content, encoding="utf-8")

        # Update report record
        report.file_path = str(file_path)
        report.status = "ready"
        report.completed_at = datetime.now(UTC)
        await db.flush()

        logger.info("Report generated: %s -> %s", report.title, file_path)
        return str(file_path)

    except Exception as e:
        report.status = "failed"
        report.error_message = str(e)
        report.completed_at = datetime.now(UTC)
        await db.flush()
        logger.error("Report generation failed for %s: %s", report_id, e, exc_info=True)
        raise


async def _gather_threat_summary(
    db: AsyncSession, parameters: dict
) -> dict:
    """Gather data for a threat summary report."""
    date_from = parameters.get("date_from")
    date_to = parameters.get("date_to")
    limit = parameters.get("limit", 50)

    # Top observables by confidence
    obs_query = select(Observable).where(Observable.is_active.is_(True))
    if date_from:
        obs_query = obs_query.where(Observable.created_at >= date_from)
    if date_to:
        obs_query = obs_query.where(Observable.created_at <= date_to)
    obs_query = obs_query.order_by(Observable.confidence_score.desc()).limit(limit)
    result = await db.execute(obs_query)
    top_observables = result.scalars().all()

    # Observable count by type
    type_counts_query = (
        select(Observable.type, func.count(Observable.id).label("count"))
        .where(Observable.is_active.is_(True))
        .group_by(Observable.type)
        .order_by(func.count(Observable.id).desc())
    )
    type_result = await db.execute(type_counts_query)
    type_counts = [
        {"type": row[0].value if hasattr(row[0], "value") else str(row[0]), "count": row[1]}
        for row in type_result.all()
    ]

    # Recent threat actors
    ta_query = select(ThreatActor).order_by(ThreatActor.updated_at.desc()).limit(10)
    ta_result = await db.execute(ta_query)
    threat_actors = ta_result.scalars().all()

    # Active campaigns
    camp_query = (
        select(Campaign)
        .where(Campaign.status == "active")
        .order_by(Campaign.updated_at.desc())
        .limit(10)
    )
    camp_result = await db.execute(camp_query)
    campaigns = camp_result.scalars().all()

    # Recent correlation events
    corr_query = (
        select(CorrelationEvent)
        .order_by(CorrelationEvent.correlated_at.desc())
        .limit(20)
    )
    corr_result = await db.execute(corr_query)
    correlations = corr_result.scalars().all()

    # Total observable count
    total_count = await db.scalar(
        select(func.count(Observable.id)).where(Observable.is_active.is_(True))
    ) or 0

    return {
        "top_observables": top_observables,
        "type_counts": type_counts,
        "threat_actors": threat_actors,
        "campaigns": campaigns,
        "correlations": correlations,
        "total_observable_count": total_count,
        "date_from": date_from or "All time",
        "date_to": date_to or "Present",
    }


async def _gather_observable_report(
    db: AsyncSession, parameters: dict
) -> dict:
    """Gather data for an observable report."""
    observable_id = parameters.get("observable_id")
    if not observable_id:
        raise ValueError("observable_id parameter is required for observable_report")

    obs_uuid = uuid.UUID(observable_id)
    observable = await db.get(Observable, obs_uuid)
    if not observable:
        raise ValueError(f"Observable not found: {observable_id}")

    # Enrichment history
    enrich_query = (
        select(EnrichmentRun)
        .where(EnrichmentRun.observable_id == obs_uuid)
        .order_by(EnrichmentRun.created_at.desc())
    )
    enrich_result = await db.execute(enrich_query)
    enrichments = enrich_result.scalars().all()

    # Relationships
    rel_query = select(ObservableRelationship).where(
        (ObservableRelationship.source_id == obs_uuid)
        | (ObservableRelationship.target_id == obs_uuid)
    )
    rel_result = await db.execute(rel_query)
    relationships = rel_result.unique().scalars().all()

    # Correlation events
    corr_query = (
        select(CorrelationEvent)
        .where(CorrelationEvent.observable_id == obs_uuid)
        .order_by(CorrelationEvent.correlated_at.desc())
    )
    corr_result = await db.execute(corr_query)
    correlations = corr_result.scalars().all()

    return {
        "observable": observable,
        "enrichments": enrichments,
        "relationships": relationships,
        "correlations": correlations,
    }


async def _gather_campaign_brief(
    db: AsyncSession, parameters: dict
) -> dict:
    """Gather data for a campaign brief report."""
    campaign_id = parameters.get("campaign_id")
    if not campaign_id:
        raise ValueError("campaign_id parameter is required for campaign_brief")

    camp_uuid = uuid.UUID(campaign_id)
    campaign = await db.get(Campaign, camp_uuid)
    if not campaign:
        raise ValueError(f"Campaign not found: {campaign_id}")

    # Linked observables (already loaded via selectin on the Campaign model)
    observables = campaign.observables or []

    # Linked threat actor
    threat_actor = campaign.threat_actor

    # All threat actors linked to the campaign's observables
    obs_ids = [o.id for o in observables]
    linked_actors = []
    if obs_ids:
        ta_query = (
            select(ThreatActor)
            .join(threat_actor_observables)
            .where(threat_actor_observables.c.observable_id.in_(obs_ids))
            .distinct()
        )
        ta_result = await db.execute(ta_query)
        linked_actors = list(ta_result.scalars().all())

    return {
        "campaign": campaign,
        "observables": observables,
        "threat_actor": threat_actor,
        "linked_actors": linked_actors,
    }
