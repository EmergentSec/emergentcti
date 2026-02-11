import logging
import uuid

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cti.models.attack import (
    AttackTactic,
    AttackTechnique,
    ObservableTechnique,
    attack_technique_tactics,
)
from cti.schemas.attack import (
    HeatmapCell,
    HeatmapResponse,
    TacticResponse,
)

logger = logging.getLogger(__name__)

MITRE_ATTACK_URL = (
    "https://raw.githubusercontent.com/mitre/cti"
    "/master/enterprise-attack/enterprise-attack.json"
)

# Standard ATT&CK tactic ordering (Enterprise matrix)
TACTIC_ORDER: dict[str, int] = {
    "reconnaissance": 0,
    "resource-development": 1,
    "initial-access": 2,
    "execution": 3,
    "persistence": 4,
    "privilege-escalation": 5,
    "defense-evasion": 6,
    "credential-access": 7,
    "discovery": 8,
    "lateral-movement": 9,
    "collection": 10,
    "command-and-control": 11,
    "exfiltration": 12,
    "impact": 13,
}


def _is_deprecated_or_revoked(obj: dict) -> bool:
    """Check if a STIX object is deprecated or revoked."""
    return obj.get("x_mitre_deprecated", False) or obj.get(
        "revoked", False
    )


def _get_external_id(obj: dict) -> str | None:
    """Extract the primary MITRE external_id from a STIX object."""
    refs = obj.get("external_references", [])
    for ref in refs:
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def _get_mitre_url(obj: dict) -> str | None:
    """Extract the MITRE ATT&CK URL from a STIX object."""
    refs = obj.get("external_references", [])
    for ref in refs:
        if ref.get("source_name") == "mitre-attack":
            return ref.get("url")
    return None


async def seed_attack_data(db: AsyncSession) -> None:
    """Download and parse the MITRE ATT&CK Enterprise matrix.

    Only seeds if the attack_tactics table is empty (idempotent).
    """
    count_result = await db.execute(
        select(func.count(AttackTactic.id))
    )
    existing_count = count_result.scalar_one()
    if existing_count > 0:
        logger.info(
            "ATT&CK data already seeded (%d tactics), skipping",
            existing_count,
        )
        return

    logger.info("Downloading MITRE ATT&CK Enterprise data...")
    await _load_attack_data(db)
    logger.info("ATT&CK data seeding complete")


async def sync_attack_data(db: AsyncSession) -> None:
    """Force re-sync: truncate existing data and re-seed."""
    logger.info("Truncating existing ATT&CK data...")

    # Delete in dependency order
    await db.execute(delete(ObservableTechnique))
    await db.execute(attack_technique_tactics.delete())
    await db.execute(delete(AttackTechnique))
    await db.execute(delete(AttackTactic))
    await db.flush()

    logger.info("Re-downloading MITRE ATT&CK Enterprise data...")
    await _load_attack_data(db)
    logger.info("ATT&CK data sync complete")


async def _load_attack_data(db: AsyncSession) -> None:
    """Fetch the STIX bundle and populate tactics and techniques."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(MITRE_ATTACK_URL)
        response.raise_for_status()
        bundle = response.json()

    objects = bundle.get("objects", [])

    # --- Parse tactics ---
    tactic_by_shortname: dict[str, AttackTactic] = {}
    for obj in objects:
        if obj.get("type") != "x-mitre-tactic":
            continue
        if _is_deprecated_or_revoked(obj):
            continue

        external_id = _get_external_id(obj)
        if not external_id:
            continue

        short_name = obj.get("x_mitre_shortname", "")
        order = TACTIC_ORDER.get(short_name, 99)

        tactic = AttackTactic(
            external_id=external_id,
            name=obj.get("name", ""),
            description=obj.get("description"),
            url=_get_mitre_url(obj),
            short_name=short_name,
            order=order,
        )
        db.add(tactic)
        tactic_by_shortname[short_name] = tactic

    await db.flush()

    # --- Parse techniques (parents first, then subtechniques) ---
    technique_data: list[dict] = []
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        if _is_deprecated_or_revoked(obj):
            continue

        external_id = _get_external_id(obj)
        if not external_id:
            continue

        technique_data.append(obj)

    # Sort so parent techniques come before subtechniques
    technique_data.sort(
        key=lambda o: o.get("x_mitre_is_subtechnique", False)
    )

    technique_by_ext_id: dict[str, AttackTechnique] = {}

    for obj in technique_data:
        external_id = _get_external_id(obj)
        if not external_id:
            continue

        is_sub = obj.get("x_mitre_is_subtechnique", False)

        # Determine parent for subtechniques (T1566.001 -> T1566)
        parent_id: uuid.UUID | None = None
        if is_sub and "." in external_id:
            parent_ext_id = external_id.split(".")[0]
            parent = technique_by_ext_id.get(parent_ext_id)
            if parent:
                parent_id = parent.id

        technique = AttackTechnique(
            external_id=external_id,
            name=obj.get("name", ""),
            description=obj.get("description"),
            is_subtechnique=is_sub,
            parent_id=parent_id,
            url=_get_mitre_url(obj),
        )
        db.add(technique)
        await db.flush()  # get the id assigned

        technique_by_ext_id[external_id] = technique

        # Link technique to tactics via kill_chain_phases
        phases = obj.get("kill_chain_phases", [])
        for phase in phases:
            if phase.get("kill_chain_name") != "mitre-attack":
                continue
            phase_name = phase.get("phase_name", "")
            tactic = tactic_by_shortname.get(phase_name)
            if tactic:
                await db.execute(
                    attack_technique_tactics.insert().values(
                        technique_id=technique.id,
                        tactic_id=tactic.id,
                    )
                )

    await db.flush()


async def list_tactics(
    db: AsyncSession,
) -> list[AttackTactic]:
    """Return all tactics ordered by display order."""
    result = await db.execute(
        select(AttackTactic).order_by(AttackTactic.order)
    )
    return list(result.scalars().all())


async def list_techniques(
    db: AsyncSession,
    tactic_id: uuid.UUID | None = None,
) -> list[AttackTechnique]:
    """Return techniques, optionally filtered by tactic."""
    query = select(AttackTechnique).options(
        joinedload(AttackTechnique.tactics)
    )

    if tactic_id:
        query = query.join(
            attack_technique_tactics,
            AttackTechnique.id
            == attack_technique_tactics.c.technique_id,
        ).where(
            attack_technique_tactics.c.tactic_id == tactic_id
        )

    query = query.order_by(AttackTechnique.external_id)
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def map_observable_to_technique(
    db: AsyncSession,
    observable_id: uuid.UUID,
    technique_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> ObservableTechnique:
    """Create an ObservableTechnique mapping entry."""
    mapping = ObservableTechnique(
        observable_id=observable_id,
        technique_id=technique_id,
        added_by=user_id,
    )
    db.add(mapping)
    await db.flush()
    await db.refresh(mapping, ["technique"])
    return mapping


async def unmap_observable_from_technique(
    db: AsyncSession,
    observable_id: uuid.UUID,
    technique_id: uuid.UUID,
) -> bool:
    """Delete an ObservableTechnique mapping. Returns True if deleted."""
    result = await db.execute(
        select(ObservableTechnique).where(
            ObservableTechnique.observable_id == observable_id,
            ObservableTechnique.technique_id == technique_id,
        )
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        return False
    await db.delete(mapping)
    await db.flush()
    return True


async def get_observable_techniques(
    db: AsyncSession,
    observable_id: uuid.UUID,
) -> list[ObservableTechnique]:
    """List techniques mapped to an observable."""
    result = await db.execute(
        select(ObservableTechnique)
        .options(joinedload(ObservableTechnique.technique))
        .where(
            ObservableTechnique.observable_id == observable_id
        )
        .order_by(ObservableTechnique.created_at)
    )
    return list(result.unique().scalars().all())


async def get_heatmap_data(
    db: AsyncSession,
) -> HeatmapResponse:
    """Build heatmap data: count observables per technique per tactic."""
    # Get all tactics for the response
    tactics = await list_tactics(db)
    tactic_responses = [
        TacticResponse.model_validate(t) for t in tactics
    ]

    # Query: count observable mappings per technique, joined to tactics
    stmt = (
        select(
            AttackTactic.external_id.label("tactic_ext_id"),
            AttackTactic.name.label("tactic_name"),
            AttackTechnique.external_id.label("tech_ext_id"),
            AttackTechnique.name.label("tech_name"),
            func.count(ObservableTechnique.id).label("obs_count"),
        )
        .select_from(ObservableTechnique)
        .join(
            AttackTechnique,
            ObservableTechnique.technique_id == AttackTechnique.id,
        )
        .join(
            attack_technique_tactics,
            AttackTechnique.id
            == attack_technique_tactics.c.technique_id,
        )
        .join(
            AttackTactic,
            attack_technique_tactics.c.tactic_id == AttackTactic.id,
        )
        .group_by(
            AttackTactic.external_id,
            AttackTactic.name,
            AttackTechnique.external_id,
            AttackTechnique.name,
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    cells = [
        HeatmapCell(
            tactic_id=row.tactic_ext_id,
            tactic_name=row.tactic_name,
            technique_id=row.tech_ext_id,
            technique_name=row.tech_name,
            count=row.obs_count,
        )
        for row in rows
    ]

    return HeatmapResponse(tactics=tactic_responses, cells=cells)
