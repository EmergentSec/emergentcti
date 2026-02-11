import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.alert import AlertEvent, AlertRule
from cti.models.observable import Observable
from cti.schemas.alert import AlertRuleCreate, AlertRuleUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------


def _rule_matches_observable(rule: AlertRule, observable: Observable) -> bool:
    """Check if all non-null conditions on the rule match the observable (AND logic)."""
    # match_type: observable type must match
    if rule.match_type is not None and observable.type.value != rule.match_type:
        return False

    # match_value_pattern: regex search on observable value
    if rule.match_value_pattern is not None:
        try:
            if not re.search(rule.match_value_pattern, observable.value):
                return False
        except re.error:
            logger.warning(
                "Invalid regex in alert rule %s: %s",
                rule.id,
                rule.match_value_pattern,
            )
            return False

    # match_tags: at least one tag in common (intersection)
    if rule.match_tags is not None:
        obs_tag_names: set[str] = set()
        for tag in observable.tags:
            if isinstance(tag, str):
                obs_tag_names.add(tag)
            elif hasattr(tag, "name"):
                obs_tag_names.add(tag.name)
        if not obs_tag_names.intersection(set(rule.match_tags)):
            return False

    # match_tlp: exact TLP match
    if rule.match_tlp is not None and observable.tlp != rule.match_tlp:
        return False

    # match_confidence_min: observable confidence must be >= threshold
    if (
        rule.match_confidence_min is not None
        and observable.confidence_score < rule.match_confidence_min
    ):
        return False

    # match_feed_id: observable must have this feed as a source
    if rule.match_feed_id is not None:
        source_ids = {s.id for s in observable.sources}
        if rule.match_feed_id not in source_ids:
            return False

    return True


def _rule_in_cooldown(rule: AlertRule) -> bool:
    """Return True if the rule was triggered too recently (within cooldown window)."""
    if rule.last_triggered_at is None:
        return False
    cooldown_until = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
    return datetime.now(UTC) < cooldown_until


# ---------------------------------------------------------------------------
# Alert evaluation
# ---------------------------------------------------------------------------


async def evaluate_alerts(
    db: AsyncSession, observable: Observable
) -> list[tuple[AlertRule, AlertEvent]]:
    """Evaluate all enabled alert rules against an observable.

    Returns a list of (rule, event) tuples for each triggered rule.
    """
    result = await db.execute(
        select(AlertRule).where(AlertRule.enabled.is_(True))
    )
    rules = result.scalars().all()

    triggered: list[tuple[AlertRule, AlertEvent]] = []

    for rule in rules:
        if _rule_in_cooldown(rule):
            continue

        if not _rule_matches_observable(rule, observable):
            continue

        # Create alert event
        now = datetime.now(UTC)
        event = AlertEvent(
            rule_id=rule.id,
            observable_id=observable.id,
            triggered_at=now,
        )
        db.add(event)

        # Update rule last_triggered_at
        rule.last_triggered_at = now

        triggered.append((rule, event))

    if triggered:
        await db.flush()

    return triggered


# ---------------------------------------------------------------------------
# CRUD for alert rules
# ---------------------------------------------------------------------------


async def create_alert_rule(
    db: AsyncSession, data: AlertRuleCreate, user_id: uuid.UUID | None = None
) -> AlertRule:
    rule = AlertRule(
        name=data.name,
        enabled=data.enabled,
        created_by=user_id,
        match_type=data.match_type,
        match_value_pattern=data.match_value_pattern,
        match_tags=data.match_tags,
        match_tlp=data.match_tlp,
        match_confidence_min=data.match_confidence_min,
        match_feed_id=data.match_feed_id,
        notification_channels=data.notification_channels,
        cooldown_minutes=data.cooldown_minutes,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


async def list_alert_rules(db: AsyncSession) -> list[AlertRule]:
    result = await db.execute(select(AlertRule).order_by(AlertRule.name))
    return list(result.scalars().all())


async def get_alert_rule(db: AsyncSession, rule_id: uuid.UUID) -> AlertRule | None:
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    return result.scalar_one_or_none()


async def update_alert_rule(
    db: AsyncSession, rule_id: uuid.UUID, data: AlertRuleUpdate
) -> AlertRule | None:
    rule = await get_alert_rule(db, rule_id)
    if not rule:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_alert_rule(db: AsyncSession, rule_id: uuid.UUID) -> bool:
    rule = await get_alert_rule(db, rule_id)
    if not rule:
        return False
    await db.delete(rule)
    await db.flush()
    return True


# ---------------------------------------------------------------------------
# Alert event queries
# ---------------------------------------------------------------------------


async def list_alert_events(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    rule_id: uuid.UUID | None = None,
) -> tuple[list[dict], int]:
    """Return paginated alert events with joined rule name and observable value."""
    query = (
        select(
            AlertEvent,
            AlertRule.name.label("rule_name"),
            Observable.value.label("observable_value"),
        )
        .join(AlertRule, AlertEvent.rule_id == AlertRule.id, isouter=True)
        .join(Observable, AlertEvent.observable_id == Observable.id, isouter=True)
    )

    count_query = select(func.count()).select_from(AlertEvent)

    if rule_id is not None:
        query = query.where(AlertEvent.rule_id == rule_id)
        count_query = count_query.where(AlertEvent.rule_id == rule_id)

    # Total count
    total = await db.scalar(count_query) or 0

    # Paginated results
    offset = (page - 1) * size
    query = query.order_by(AlertEvent.triggered_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    rows = result.all()

    items: list[dict] = []
    for row in rows:
        event = row[0]
        items.append({
            "id": event.id,
            "rule_id": event.rule_id,
            "observable_id": event.observable_id,
            "triggered_at": event.triggered_at,
            "notification_sent": event.notification_sent,
            "notification_error": event.notification_error,
            "rule_name": row[1],
            "observable_value": row[2],
        })

    return items, total
