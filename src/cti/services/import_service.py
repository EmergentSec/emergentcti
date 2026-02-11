"""Import service for parsing CSV and STIX 2.1 data into ObservableCreate items."""

import contextlib
import csv
import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cti.models.observable import ObservableType
from cti.schemas.observable import ObservableCreate

logger = logging.getLogger(__name__)

# Known column header aliases mapped to canonical ObservableCreate field names.
# Used for heuristic auto-detection of CSV column mappings.
_HEADER_ALIASES: dict[str, str] = {
    # type field
    "type": "type",
    "observable_type": "type",
    "indicator_type": "type",
    "ioc_type": "type",
    "obs_type": "type",
    # value field
    "value": "value",
    "indicator": "value",
    "ioc": "value",
    "ioc_value": "value",
    "observable": "value",
    "observable_value": "value",
    "artifact": "value",
    "ip": "value",
    "domain": "value",
    "url": "value",
    "hash": "value",
    "email": "value",
    # confidence_score field
    "confidence_score": "confidence_score",
    "confidence": "confidence_score",
    "score": "confidence_score",
    "rating": "confidence_score",
    # tlp field
    "tlp": "tlp",
    "tlp_level": "tlp",
    "traffic_light_protocol": "tlp",
    # first_seen field
    "first_seen": "first_seen",
    "first_observed": "first_seen",
    "firstseen": "first_seen",
    "created": "first_seen",
    "date_added": "first_seen",
    # last_seen field
    "last_seen": "last_seen",
    "last_observed": "last_seen",
    "lastseen": "last_seen",
    "updated": "last_seen",
    "date_modified": "last_seen",
    # category field
    "category": "category",
    "threat_type": "category",
    "malware_type": "category",
    "classification": "category",
    # description field
    "description": "description",
    "comment": "description",
    "comments": "description",
    "notes": "description",
    "note": "description",
    # tags field
    "tags": "tags",
    "tag": "tags",
    "labels": "tags",
    "label": "tags",
}

# Valid ObservableType values for quick lookup
_VALID_TYPES: set[str] = {e.value for e in ObservableType}


def detect_csv_columns(headers: list[str]) -> dict[str, str]:
    """Heuristic auto-detection mapping CSV headers to observable fields.

    Returns a dict where keys are CSV column headers and values are
    canonical field names (type, value, confidence_score, etc.).
    Unrecognized headers are excluded from the mapping.
    """
    mapping: dict[str, str] = {}
    used_fields: set[str] = set()

    for header in headers:
        normalized = header.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized in _HEADER_ALIASES:
            field = _HEADER_ALIASES[normalized]
            # Avoid mapping multiple columns to the same field
            if field not in used_fields:
                mapping[header] = field
                used_fields.add(field)

    return mapping


def _parse_type(raw_value: str) -> ObservableType | None:
    """Parse a string into an ObservableType, handling common aliases."""
    cleaned = raw_value.strip().lower()

    # Direct match
    if cleaned in _VALID_TYPES:
        return ObservableType(cleaned)

    # Common aliases
    type_aliases: dict[str, str] = {
        "ip": "ip-addr",
        "ipv4": "ip-addr",
        "ipv6": "ip-addr",
        "ip_addr": "ip-addr",
        "ip-address": "ip-addr",
        "ip_address": "ip-addr",
        "ipaddr": "ip-addr",
        "domain": "domain-name",
        "domain_name": "domain-name",
        "hostname": "domain-name",
        "fqdn": "domain-name",
        "url": "url",
        "uri": "url",
        "hash": "file-hash",
        "file_hash": "file-hash",
        "filehash": "file-hash",
        "md5": "file-hash",
        "sha1": "file-hash",
        "sha256": "file-hash",
        "sha512": "file-hash",
        "email": "email-addr",
        "email_addr": "email-addr",
        "email-address": "email-addr",
        "email_address": "email-addr",
        "command": "command-line",
        "command_line": "command-line",
        "cmd": "command-line",
        "useragent": "user-agent",
        "user_agent": "user-agent",
        "ua": "user-agent",
        "cert": "certificate",
        "certificate": "certificate",
        "asn": "asn",
        "cidr": "cidr",
        "subnet": "cidr",
    }

    mapped = type_aliases.get(cleaned)
    if mapped:
        return ObservableType(mapped)

    return None


def _parse_confidence(raw_value: str) -> int:
    """Parse a confidence score string to an integer, clamped to 0-100."""
    try:
        val = int(float(raw_value.strip()))
        return max(0, min(100, val))
    except (ValueError, TypeError):
        return 50


def _parse_tags(raw_value: str) -> list[str]:
    """Parse a tags string (semicolon or comma separated) into a list."""
    if not raw_value or not raw_value.strip():
        return []
    # Try semicolon first, then comma
    if ";" in raw_value:
        return [t.strip() for t in raw_value.split(";") if t.strip()]
    return [t.strip() for t in raw_value.split(",") if t.strip()]


def parse_csv(
    file_content: str,
    column_mapping: dict[str, str],
) -> tuple[list[ObservableCreate], list[str]]:
    """Parse CSV rows into ObservableCreate items using the given column mapping.

    Returns a tuple of (successfully_parsed_items, error_messages).
    Invalid rows are skipped with an error message rather than crashing.
    """
    items: list[ObservableCreate] = []
    errors: list[str] = []

    reader = csv.DictReader(io.StringIO(file_content))
    if not reader.fieldnames:
        errors.append("CSV file has no headers")
        return items, errors

    # Invert mapping: field_name -> csv_column_header
    field_to_column: dict[str, str] = {v: k for k, v in column_mapping.items()}

    for row_num, row in enumerate(reader, start=2):  # row 1 is header
        try:
            # Extract type
            type_col = field_to_column.get("type")
            raw_type = row.get(type_col, "").strip() if type_col else ""

            # Extract value
            value_col = field_to_column.get("value")
            raw_value = row.get(value_col, "").strip() if value_col else ""

            if not raw_value:
                errors.append(f"Row {row_num}: missing value")
                continue

            # Parse type
            obs_type: ObservableType | None = None
            if raw_type:
                obs_type = _parse_type(raw_type)
                if obs_type is None:
                    errors.append(f"Row {row_num}: unknown type '{raw_type}'")
                    continue
            else:
                # If no type column, try to infer from the value column header
                if value_col:
                    inferred = _parse_type(value_col)
                    if inferred:
                        obs_type = inferred
                if obs_type is None:
                    errors.append(f"Row {row_num}: no type specified and cannot infer")
                    continue

            # Build kwargs for ObservableCreate
            kwargs: dict[str, Any] = {
                "type": obs_type,
                "value": raw_value,
            }

            # confidence_score
            conf_col = field_to_column.get("confidence_score")
            if conf_col and row.get(conf_col, "").strip():
                kwargs["confidence_score"] = _parse_confidence(row[conf_col])

            # tlp
            tlp_col = field_to_column.get("tlp")
            if tlp_col and row.get(tlp_col, "").strip():
                kwargs["tlp"] = row[tlp_col].strip().lower()

            # first_seen
            first_col = field_to_column.get("first_seen")
            if first_col and row.get(first_col, "").strip():
                with contextlib.suppress(ValueError):
                    kwargs["first_seen"] = datetime.fromisoformat(row[first_col].strip())

            # last_seen
            last_col = field_to_column.get("last_seen")
            if last_col and row.get(last_col, "").strip():
                with contextlib.suppress(ValueError):
                    kwargs["last_seen"] = datetime.fromisoformat(row[last_col].strip())

            # category
            cat_col = field_to_column.get("category")
            if cat_col and row.get(cat_col, "").strip():
                kwargs["category"] = row[cat_col].strip()

            # description
            desc_col = field_to_column.get("description")
            if desc_col and row.get(desc_col, "").strip():
                kwargs["description"] = row[desc_col].strip()

            # tags
            tags_col = field_to_column.get("tags")
            if tags_col and row.get(tags_col, "").strip():
                kwargs["tags"] = _parse_tags(row[tags_col])

            item = ObservableCreate(**kwargs)
            items.append(item)

        except Exception as exc:
            errors.append(f"Row {row_num}: {exc}")

    return items, errors


def preview_csv(
    file_content: str,
    column_mapping: dict[str, str] | None = None,
    limit: int = 50,
) -> tuple[dict[str, str], list[dict], int, list[str]]:
    """Preview a CSV file, returning detected mapping, first N parsed rows,
    total row count, and any errors.

    Returns a tuple of (detected_mapping, preview_rows, total_rows, errors).
    """
    reader = csv.DictReader(io.StringIO(file_content))
    headers = list(reader.fieldnames or [])

    # Auto-detect columns if no mapping provided
    detected_mapping = detect_csv_columns(headers)
    effective_mapping = column_mapping if column_mapping else detected_mapping

    # Count total rows
    all_rows = list(reader)
    total_rows = len(all_rows)

    # Parse limited rows for preview
    limited_content_lines = file_content.strip().split("\n")
    # Reconstruct CSV with only header + limit rows
    preview_lines = limited_content_lines[: limit + 1]  # header + N rows
    preview_content = "\n".join(preview_lines)

    items, errors = parse_csv(preview_content, effective_mapping)

    # Convert parsed items to dicts for the preview response
    preview_rows: list[dict] = []
    for item in items:
        row_dict: dict[str, Any] = {
            "type": item.type.value,
            "value": item.value,
            "confidence_score": item.confidence_score,
            "tlp": item.tlp,
        }
        if item.first_seen:
            row_dict["first_seen"] = item.first_seen.isoformat()
        if item.last_seen:
            row_dict["last_seen"] = item.last_seen.isoformat()
        if item.category:
            row_dict["category"] = item.category
        if item.description:
            row_dict["description"] = item.description
        if item.tags:
            row_dict["tags"] = item.tags
        preview_rows.append(row_dict)

    return detected_mapping, preview_rows, total_rows, errors


@dataclass
class STIXRelationship:
    source_ref: str
    target_ref: str
    relationship_type: str


@dataclass
class STIXParseResult:
    observables: list[ObservableCreate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    threat_actors: list[dict] = field(default_factory=list)  # name, aliases, stix_id
    campaigns: list[dict] = field(default_factory=list)  # name, description, stix_id
    attack_patterns: list[dict] = field(default_factory=list)  # external_id, name, stix_id
    indicators: list[dict] = field(default_factory=list)  # observable_value, stix_id
    relationships: list[STIXRelationship] = field(default_factory=list)
    # Maps STIX id -> parsed observable value for correlation resolution
    stix_id_to_observable_value: dict[str, str] = field(default_factory=dict)


# Regex to extract a simple observable from a STIX indicator pattern
# e.g. [ipv4-addr:value = '1.2.3.4'] or [domain-name:value = 'evil.com']
_INDICATOR_PATTERN_RE = re.compile(
    r"\[\s*[\w-]+:value\s*=\s*'([^']+)'\s*\]"
)


def parse_stix_bundle_full(data: dict) -> STIXParseResult:
    """Parse a STIX 2.1 Bundle, extracting SCOs, SDOs, indicators, and relationships.

    This is the enhanced version that captures all correlation-relevant objects.
    """
    result = STIXParseResult()
    objects = data.get("objects", [])

    for idx, obj in enumerate(objects):
        try:
            obj_type = obj.get("type", "")
            stix_id = obj.get("id", f"object-{idx}")

            # --- SCO parsing (same as before) ---
            obs_type: ObservableType | None = None
            value: str | None = None

            confidence = obj.get("x_cti_confidence", 50)
            tlp = obj.get("x_cti_tlp", "clear")
            category = obj.get("x_cti_category")
            description = obj.get("x_cti_description")
            tags_raw = obj.get("x_cti_tags", [])
            first_seen_raw = obj.get("x_cti_first_seen")
            last_seen_raw = obj.get("x_cti_last_seen")

            if obj_type in ("ipv4-addr", "ipv6-addr"):
                obs_type = ObservableType.ip_addr
                value = obj.get("value", "")

            elif obj_type == "domain-name":
                obs_type = ObservableType.domain_name
                value = obj.get("value", "")

            elif obj_type == "url":
                obs_type = ObservableType.url
                value = obj.get("value", "")

            elif obj_type == "email-addr":
                obs_type = ObservableType.email_addr
                value = obj.get("value", "")

            elif obj_type == "file":
                hashes = obj.get("hashes", {})
                if hashes:
                    obs_type = ObservableType.file_hash
                    for algo in ("SHA-256", "SHA-1", "MD5", "SHA-512"):
                        if algo in hashes:
                            value = hashes[algo]
                            break
                    if value is None:
                        value = next(iter(hashes.values()))
                else:
                    result.errors.append(f"Object {stix_id}: file object has no hashes")
                    continue

            elif obj_type == "x-cti-observable":
                raw_type = obj.get("observable_type", "")
                value = obj.get("value", "")
                if raw_type in _VALID_TYPES:
                    obs_type = ObservableType(raw_type)
                else:
                    result.errors.append(
                        f"Object {stix_id}: unknown x-cti-observable type '{raw_type}'"
                    )
                    continue

            # --- SDO: threat-actor ---
            elif obj_type == "threat-actor":
                aliases = obj.get("aliases", [])
                result.threat_actors.append({
                    "name": obj.get("name", ""),
                    "aliases": aliases if isinstance(aliases, list) else [],
                    "description": obj.get("description"),
                    "stix_id": stix_id,
                })
                continue

            # --- SDO: campaign ---
            elif obj_type == "campaign":
                result.campaigns.append({
                    "name": obj.get("name", ""),
                    "description": obj.get("description"),
                    "stix_id": stix_id,
                })
                continue

            # --- SDO: attack-pattern ---
            elif obj_type == "attack-pattern":
                external_id = None
                for ref in obj.get("external_references", []):
                    if ref.get("source_name") == "mitre-attack":
                        external_id = ref.get("external_id")
                        break
                if external_id:
                    result.attack_patterns.append({
                        "external_id": external_id,
                        "name": obj.get("name", ""),
                        "stix_id": stix_id,
                    })
                continue

            # --- SDO: indicator ---
            elif obj_type == "indicator":
                pattern = obj.get("pattern", "")
                match = _INDICATOR_PATTERN_RE.search(pattern)
                if match:
                    result.indicators.append({
                        "observable_value": match.group(1),
                        "stix_id": stix_id,
                    })
                continue

            # --- relationship ---
            elif obj_type == "relationship":
                source_ref = obj.get("source_ref", "")
                target_ref = obj.get("target_ref", "")
                rel_type = obj.get("relationship_type", "")
                if source_ref and target_ref and rel_type:
                    result.relationships.append(
                        STIXRelationship(
                            source_ref=source_ref,
                            target_ref=target_ref,
                            relationship_type=rel_type,
                        )
                    )
                continue

            else:
                # Skip non-SCO objects (e.g., identity, marking-definition)
                continue

            if not value or obs_type is None:
                result.errors.append(f"Object {stix_id}: could not extract type/value")
                continue

            # Record mapping from STIX ID to observable value
            result.stix_id_to_observable_value[stix_id] = value

            kwargs: dict[str, Any] = {
                "type": obs_type,
                "value": value,
                "confidence_score": max(0, min(100, int(confidence))),
                "tlp": str(tlp),
            }

            if category:
                kwargs["category"] = str(category)
            if description:
                kwargs["description"] = str(description)
            if tags_raw and isinstance(tags_raw, list):
                kwargs["tags"] = [str(t) for t in tags_raw]

            if first_seen_raw:
                with contextlib.suppress(ValueError):
                    kwargs["first_seen"] = datetime.fromisoformat(str(first_seen_raw))

            if last_seen_raw:
                with contextlib.suppress(ValueError):
                    kwargs["last_seen"] = datetime.fromisoformat(str(last_seen_raw))

            item = ObservableCreate(**kwargs)
            result.observables.append(item)

        except Exception as exc:
            result.errors.append(f"Object {idx}: {exc}")

    return result


def parse_stix_bundle(data: dict) -> tuple[list[ObservableCreate], list[str]]:
    """Parse a STIX 2.1 Bundle and extract SCOs as ObservableCreate items.

    Wrapper around parse_stix_bundle_full for backward compatibility.

    Returns a tuple of (parsed_items, error_messages).
    """
    full_result = parse_stix_bundle_full(data)
    return full_result.observables, full_result.errors


async def process_stix_correlations(
    db: AsyncSession,
    parse_result: STIXParseResult,
    observable_id_map: dict[str, uuid.UUID],
) -> list:
    """Process STIX SDOs and relationships to create correlation links.

    Args:
        db: Async database session.
        parse_result: The full parse result from parse_stix_bundle_full.
        observable_id_map: Maps observable value -> database UUID.

    Returns a list of CorrelationEvent records created.
    """
    from cti.models.attack import AttackTechnique
    from cti.models.campaign import Campaign
    from cti.models.correlation import CorrelationEvent
    from cti.models.threat_actor import ThreatActor
    from cti.schemas.campaign import CampaignCreate
    from cti.schemas.threat_actor import ThreatActorCreate
    from cti.services.attack_service import map_observable_to_technique
    from cti.services.campaign_service import (
        create_campaign as create_campaign_svc,
    )
    from cti.services.campaign_service import (
        link_observable as link_campaign_observable,
    )
    from cti.services.threat_actor_service import (
        create_threat_actor as create_actor_svc,
    )
    from cti.services.threat_actor_service import (
        link_observable as link_actor_observable,
    )

    events: list[CorrelationEvent] = []

    # Build STIX ID -> entity ID maps for relationship resolution
    stix_id_to_actor_id: dict[str, uuid.UUID] = {}
    stix_id_to_campaign_id: dict[str, uuid.UUID] = {}
    stix_id_to_technique_id: dict[str, uuid.UUID] = {}
    stix_id_to_observable_id: dict[str, uuid.UUID] = {}

    # Map SCO STIX IDs to observable IDs
    for stix_id, obs_value in parse_result.stix_id_to_observable_value.items():
        if obs_value in observable_id_map:
            stix_id_to_observable_id[stix_id] = observable_id_map[obs_value]

    # Map indicator STIX IDs to observable IDs
    for indicator in parse_result.indicators:
        obs_value = indicator["observable_value"]
        if obs_value in observable_id_map:
            stix_id_to_observable_id[indicator["stix_id"]] = observable_id_map[obs_value]

    # --- Resolve threat actors by name/aliases, auto-create if needed ---
    for actor_data in parse_result.threat_actors:
        name = actor_data["name"]
        if not name:
            continue

        # Search by name
        stmt = select(ThreatActor).where(ThreatActor.name == name)
        result = await db.execute(stmt)
        actor = result.scalar_one_or_none()

        if not actor:
            # Search by alias
            aliases = actor_data.get("aliases", [])
            for alias in aliases:
                stmt = select(ThreatActor).where(ThreatActor.name == alias)
                result = await db.execute(stmt)
                actor = result.scalar_one_or_none()
                if actor:
                    break

        if not actor:
            # Auto-create
            create_data = ThreatActorCreate(
                name=name,
                aliases=actor_data.get("aliases"),
                description=actor_data.get("description"),
            )
            actor = await create_actor_svc(db, create_data)

        stix_id_to_actor_id[actor_data["stix_id"]] = actor.id

    # --- Resolve campaigns by name, auto-create if needed ---
    for campaign_data in parse_result.campaigns:
        name = campaign_data["name"]
        if not name:
            continue

        stmt = select(Campaign).where(Campaign.name == name)
        result = await db.execute(stmt)
        campaign = result.scalar_one_or_none()

        if not campaign:
            create_data = CampaignCreate(
                name=name,
                description=campaign_data.get("description"),
            )
            campaign = await create_campaign_svc(db, create_data)

        stix_id_to_campaign_id[campaign_data["stix_id"]] = campaign.id

    # --- Resolve attack patterns by external_id (no auto-create) ---
    for pattern_data in parse_result.attack_patterns:
        external_id = pattern_data["external_id"]
        stmt = select(AttackTechnique).where(
            AttackTechnique.external_id == external_id
        )
        result = await db.execute(stmt)
        technique = result.scalar_one_or_none()
        if technique:
            stix_id_to_technique_id[pattern_data["stix_id"]] = technique.id

    # --- Process relationships ---
    for rel in parse_result.relationships:
        source_ref = rel.source_ref
        target_ref = rel.target_ref

        # Determine observable ID (could be source or target)
        obs_id: uuid.UUID | None = None
        entity_ref: str | None = None

        if source_ref in stix_id_to_observable_id:
            obs_id = stix_id_to_observable_id[source_ref]
            entity_ref = target_ref
        elif target_ref in stix_id_to_observable_id:
            obs_id = stix_id_to_observable_id[target_ref]
            entity_ref = source_ref

        if obs_id is None or entity_ref is None:
            continue

        # Link to threat actor
        if entity_ref in stix_id_to_actor_id:
            actor_id = stix_id_to_actor_id[entity_ref]
            await link_actor_observable(db, actor_id, obs_id)
            event = CorrelationEvent(
                rule_id=None,
                observable_id=obs_id,
                action_type="link_threat_actor",
                target_id=actor_id,
                source="stix_import",
            )
            db.add(event)
            events.append(event)

        # Link to campaign
        elif entity_ref in stix_id_to_campaign_id:
            campaign_id = stix_id_to_campaign_id[entity_ref]
            await link_campaign_observable(db, campaign_id, obs_id)
            event = CorrelationEvent(
                rule_id=None,
                observable_id=obs_id,
                action_type="link_campaign",
                target_id=campaign_id,
                source="stix_import",
            )
            db.add(event)
            events.append(event)

        # Map to technique
        elif entity_ref in stix_id_to_technique_id:
            technique_id = stix_id_to_technique_id[entity_ref]
            try:
                await map_observable_to_technique(db, obs_id, technique_id)
                event = CorrelationEvent(
                    rule_id=None,
                    observable_id=obs_id,
                    action_type="map_technique",
                    target_id=technique_id,
                    source="stix_import",
                )
                db.add(event)
                events.append(event)
            except IntegrityError:
                await db.rollback()

    if events:
        await db.flush()

    return events
