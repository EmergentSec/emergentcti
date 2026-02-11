import logging
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cti.models.correlation import CorrelationActionType, CorrelationEvent, CorrelationRule
from cti.models.observable import Observable
from cti.schemas.correlation import CorrelationRuleCreate, CorrelationRuleUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule matching (mirrors alert_service._rule_matches_observable)
# ---------------------------------------------------------------------------


def _rule_matches_observable(rule: CorrelationRule, observable: Observable) -> bool:
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
                "Invalid regex in correlation rule %s: %s",
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


# ---------------------------------------------------------------------------
# Linking helpers
# ---------------------------------------------------------------------------


async def _apply_action(
    db: AsyncSession, rule: CorrelationRule, observable: Observable
) -> uuid.UUID | None:
    """Execute the correlation action and return the target entity id, or None on failure."""
    action = rule.action_type

    if action == CorrelationActionType.link_threat_actor:
        from cti.services.threat_actor_service import link_observable as link_actor_observable

        target_id = rule.target_threat_actor_id
        if target_id is None:
            return None
        linked = await link_actor_observable(db, target_id, observable.id)
        return target_id if linked else None

    if action == CorrelationActionType.link_campaign:
        from cti.services.campaign_service import link_observable as link_campaign_observable

        target_id = rule.target_campaign_id
        if target_id is None:
            return None
        linked = await link_campaign_observable(db, target_id, observable.id)
        return target_id if linked else None

    if action == CorrelationActionType.map_technique:
        from cti.services.attack_service import map_observable_to_technique

        target_id = rule.target_technique_id
        if target_id is None:
            return None
        try:
            await map_observable_to_technique(db, observable.id, target_id)
        except IntegrityError:
            # Duplicate mapping is a no-op
            await db.rollback()
        return target_id

    return None


# ---------------------------------------------------------------------------
# Correlation evaluation
# ---------------------------------------------------------------------------


async def evaluate_correlations(
    db: AsyncSession, observable: Observable
) -> list[CorrelationEvent]:
    """Evaluate all enabled correlation rules against a single observable.

    Returns a list of CorrelationEvent records created.
    """
    result = await db.execute(
        select(CorrelationRule).where(CorrelationRule.enabled.is_(True))
    )
    rules = result.scalars().all()

    events: list[CorrelationEvent] = []

    for rule in rules:
        if not _rule_matches_observable(rule, observable):
            continue

        target_id = await _apply_action(db, rule, observable)
        if target_id is None:
            continue

        event = CorrelationEvent(
            rule_id=rule.id,
            observable_id=observable.id,
            action_type=rule.action_type,
            target_id=target_id,
            source="rule",
        )
        db.add(event)
        events.append(event)

    if events:
        await db.flush()

    return events


async def evaluate_correlations_batch(
    db: AsyncSession,
    observable_ids: list[uuid.UUID],
    feed_id: uuid.UUID | None = None,
) -> int:
    """Batch version of correlation evaluation for worker tasks.

    Loads observables with tags and sources eagerly, pre-filters rules by
    match_feed_id, and returns the total number of correlation events created.
    """
    if not observable_ids:
        return 0

    # Load observables with relationships
    obs_result = await db.execute(
        select(Observable)
        .options(joinedload(Observable.tags), joinedload(Observable.sources))
        .where(Observable.id.in_(observable_ids))
    )
    observables = list(obs_result.unique().scalars().all())

    if not observables:
        return 0

    # Load enabled rules
    rule_query = select(CorrelationRule).where(CorrelationRule.enabled.is_(True))
    rule_result = await db.execute(rule_query)
    all_rules = list(rule_result.scalars().all())

    # Pre-filter: if feed_id is provided, only consider rules that either
    # have no match_feed_id or match the current feed
    if feed_id is not None:
        rules = [
            r for r in all_rules if r.match_feed_id is None or r.match_feed_id == feed_id
        ]
    else:
        rules = all_rules

    total_events = 0

    for observable in observables:
        for rule in rules:
            if not _rule_matches_observable(rule, observable):
                continue

            target_id = await _apply_action(db, rule, observable)
            if target_id is None:
                continue

            event = CorrelationEvent(
                rule_id=rule.id,
                observable_id=observable.id,
                action_type=rule.action_type,
                target_id=target_id,
                source="rule",
            )
            db.add(event)
            total_events += 1

    if total_events:
        await db.flush()

    return total_events


# ---------------------------------------------------------------------------
# CRUD for correlation rules
# ---------------------------------------------------------------------------


async def create_rule(
    db: AsyncSession, data: CorrelationRuleCreate, user_id: uuid.UUID | None = None
) -> CorrelationRule:
    rule = CorrelationRule(
        name=data.name,
        enabled=data.enabled,
        created_by=user_id,
        match_type=data.match_type,
        match_value_pattern=data.match_value_pattern,
        match_tags=data.match_tags,
        match_tlp=data.match_tlp,
        match_confidence_min=data.match_confidence_min,
        match_feed_id=data.match_feed_id,
        action_type=data.action_type,
        target_threat_actor_id=data.target_threat_actor_id,
        target_campaign_id=data.target_campaign_id,
        target_technique_id=data.target_technique_id,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


async def list_rules(db: AsyncSession) -> list[CorrelationRule]:
    result = await db.execute(select(CorrelationRule).order_by(CorrelationRule.name))
    return list(result.scalars().all())


async def get_rule(db: AsyncSession, rule_id: uuid.UUID) -> CorrelationRule | None:
    result = await db.execute(
        select(CorrelationRule).where(CorrelationRule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def update_rule(
    db: AsyncSession, rule_id: uuid.UUID, data: CorrelationRuleUpdate
) -> CorrelationRule | None:
    rule = await get_rule(db, rule_id)
    if not rule:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.flush()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule_id: uuid.UUID) -> bool:
    rule = await get_rule(db, rule_id)
    if not rule:
        return False
    await db.delete(rule)
    await db.flush()
    return True


# ---------------------------------------------------------------------------
# Correlation event queries
# ---------------------------------------------------------------------------


async def list_events(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    rule_id: uuid.UUID | None = None,
) -> tuple[list[dict], int]:
    """Return paginated correlation events with joined rule name and observable value."""
    query = (
        select(
            CorrelationEvent,
            CorrelationRule.name.label("rule_name"),
            Observable.value.label("observable_value"),
        )
        .join(CorrelationRule, CorrelationEvent.rule_id == CorrelationRule.id, isouter=True)
        .join(Observable, CorrelationEvent.observable_id == Observable.id, isouter=True)
    )

    count_query = select(func.count()).select_from(CorrelationEvent)

    if rule_id is not None:
        query = query.where(CorrelationEvent.rule_id == rule_id)
        count_query = count_query.where(CorrelationEvent.rule_id == rule_id)

    # Total count
    total = await db.scalar(count_query) or 0

    # Paginated results
    offset = (page - 1) * size
    query = query.order_by(CorrelationEvent.correlated_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    rows = result.all()

    items: list[dict] = []
    for row in rows:
        event = row[0]
        items.append({
            "id": event.id,
            "rule_id": event.rule_id,
            "observable_id": event.observable_id,
            "action_type": event.action_type,
            "target_id": event.target_id,
            "correlated_at": event.correlated_at,
            "source": event.source,
            "rule_name": row[1],
            "observable_value": row[2],
        })

    return items, total
