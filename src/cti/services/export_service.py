"""Export service for converting observables to STIX 2.1, CSV, and JSON formats."""

import csv
import io
import ipaddress
import json
import logging
import uuid
from datetime import datetime
from typing import Any

import stix2

from cti.models.observable import Observable, ObservableType
from cti.models.relationship import ObservableRelationship

logger = logging.getLogger(__name__)

# Mapping from hash length to hash algorithm name for STIX File objects
_HASH_LENGTH_TO_ALGO: dict[int, str] = {
    32: "MD5",
    40: "SHA-1",
    64: "SHA-256",
    128: "SHA-512",
}


def _detect_hash_algo(value: str) -> str:
    """Detect hash algorithm based on hex string length."""
    return _HASH_LENGTH_TO_ALGO.get(len(value), "SHA-256")


def _make_deterministic_id(prefix: str, observable: Observable) -> str:
    """Create a deterministic STIX ID based on observable type+value.

    This ensures the same observable always produces the same STIX ID,
    which is important for deduplication when importing/exporting.
    """
    namespace = uuid.UUID("a]6e2809-3274-4672-b56d-72e146f39b4e")
    key = f"{observable.type.value}:{observable.value}"
    return f"{prefix}--{uuid.uuid5(namespace, key)}"


def observable_to_stix(observable: Observable) -> stix2.base._STIXBase:
    """Convert a CTI Observable to a STIX 2.1 SCO (STIX Cyber Observable).

    Maps ObservableType to the corresponding STIX 2.1 object type:
    - ip-addr -> IPv4Address or IPv6Address
    - domain-name -> DomainName
    - url -> URL
    - file-hash -> File (with hashes property)
    - email-addr -> EmailAddress
    - Others -> CustomObservable (x-cti-observable)
    """
    obs_type = observable.type
    value = observable.value

    # Build custom properties that all SCOs will carry
    custom_props: dict[str, Any] = {}
    if observable.confidence_score is not None:
        custom_props["x_cti_confidence"] = observable.confidence_score
    if observable.tlp:
        custom_props["x_cti_tlp"] = observable.tlp
    if observable.category:
        custom_props["x_cti_category"] = observable.category
    if observable.description:
        custom_props["x_cti_description"] = observable.description
    if observable.first_seen:
        custom_props["x_cti_first_seen"] = observable.first_seen.isoformat()
    if observable.last_seen:
        custom_props["x_cti_last_seen"] = observable.last_seen.isoformat()

    # Map tags
    tags = getattr(observable, "tags", None)
    if tags:
        tag_names = []
        for t in tags:
            if isinstance(t, str):
                tag_names.append(t)
            elif hasattr(t, "name"):
                tag_names.append(t.name)
        if tag_names:
            custom_props["x_cti_tags"] = tag_names

    if obs_type == ObservableType.ip_addr:
        try:
            addr = ipaddress.ip_address(value)
            if isinstance(addr, ipaddress.IPv6Address):
                return stix2.IPv6Address(
                    value=value,
                    allow_custom=True,
                    **custom_props,
                )
            return stix2.IPv4Address(
                value=value,
                allow_custom=True,
                **custom_props,
            )
        except ValueError:
            # Fallback to IPv4Address for invalid addresses
            return stix2.IPv4Address(
                value=value,
                allow_custom=True,
                **custom_props,
            )

    if obs_type == ObservableType.domain_name:
        return stix2.DomainName(
            value=value,
            allow_custom=True,
            **custom_props,
        )

    if obs_type == ObservableType.url:
        return stix2.URL(
            value=value,
            allow_custom=True,
            **custom_props,
        )

    if obs_type == ObservableType.file_hash:
        algo = _detect_hash_algo(value)
        return stix2.File(
            hashes={algo: value},
            allow_custom=True,
            **custom_props,
        )

    if obs_type == ObservableType.email_addr:
        return stix2.EmailAddress(
            value=value,
            allow_custom=True,
            **custom_props,
        )

    # For types without a direct STIX SCO mapping (command-line, user-agent,
    # certificate, asn, cidr), use a custom observable.
    return stix2.CustomObservable(
        "x-cti-observable",
        [
            ("value", stix2.properties.StringProperty(required=True)),
            ("observable_type", stix2.properties.StringProperty(required=True)),
            ("x_cti_confidence", stix2.properties.IntegerProperty()),
            ("x_cti_tlp", stix2.properties.StringProperty()),
            ("x_cti_category", stix2.properties.StringProperty()),
            ("x_cti_description", stix2.properties.StringProperty()),
            ("x_cti_first_seen", stix2.properties.StringProperty()),
            ("x_cti_last_seen", stix2.properties.StringProperty()),
            ("x_cti_tags", stix2.properties.ListProperty(stix2.properties.StringProperty())),
        ],
        id_contrib_props=["value", "observable_type"],
    )(
        value=value,
        observable_type=obs_type.value,
        allow_custom=True,
        **custom_props,
    )


def relationship_to_stix(
    relationship: ObservableRelationship,
    source_obs: Observable,
    target_obs: Observable,
) -> stix2.Relationship:
    """Convert a CTI ObservableRelationship to a STIX 2.1 Relationship (SRO).

    The source and target observables are needed to generate their STIX IDs
    for the source_ref and target_ref fields.
    """
    source_stix = observable_to_stix(source_obs)
    target_stix = observable_to_stix(target_obs)

    return stix2.Relationship(
        relationship_type=relationship.relationship_type,
        source_ref=source_stix.id,
        target_ref=target_stix.id,
        confidence=relationship.confidence,
        allow_custom=True,
    )


def export_stix_bundle(
    observables: list[Observable],
    relationships: list[ObservableRelationship] | None = None,
) -> dict:
    """Export observables and optional relationships as a STIX 2.1 Bundle.

    Returns the bundle as a JSON-serializable dict.
    """
    stix_objects: list[stix2.base._STIXBase] = []

    # Build a lookup of observable id -> Observable for relationship resolution
    obs_lookup: dict[uuid.UUID, Observable] = {}
    for obs in observables:
        obs_lookup[obs.id] = obs
        try:
            stix_obj = observable_to_stix(obs)
            stix_objects.append(stix_obj)
        except Exception:
            logger.warning("Failed to convert observable %s to STIX", obs.id, exc_info=True)

    if relationships:
        for rel in relationships:
            source = obs_lookup.get(rel.source_id)
            target = obs_lookup.get(rel.target_id)
            if source and target:
                try:
                    stix_rel = relationship_to_stix(rel, source, target)
                    stix_objects.append(stix_rel)
                except Exception:
                    logger.warning(
                        "Failed to convert relationship %s to STIX",
                        rel.id,
                        exc_info=True,
                    )

    bundle = stix2.Bundle(objects=stix_objects, allow_custom=True)
    return json.loads(bundle.serialize())


def export_csv(observables: list[Observable]) -> str:
    """Export observables as a CSV string.

    Columns: type, value, confidence_score, tlp, first_seen, last_seen,
    category, tags, sources, description
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "type",
        "value",
        "confidence_score",
        "tlp",
        "first_seen",
        "last_seen",
        "category",
        "tags",
        "sources",
        "description",
    ])

    for obs in observables:
        # Extract tag names
        tags_str = ""
        tags = getattr(obs, "tags", None)
        if tags:
            tag_names = []
            for t in tags:
                if isinstance(t, str):
                    tag_names.append(t)
                elif hasattr(t, "name"):
                    tag_names.append(t.name)
            tags_str = ";".join(tag_names)

        # Extract source/feed names
        sources_str = ""
        sources = getattr(obs, "sources", None)
        if sources:
            source_names = []
            for s in sources:
                if isinstance(s, str):
                    source_names.append(s)
                elif hasattr(s, "name"):
                    source_names.append(s.name)
            sources_str = ";".join(source_names)

        writer.writerow([
            obs.type.value if hasattr(obs.type, "value") else str(obs.type),
            obs.value,
            obs.confidence_score,
            obs.tlp,
            obs.first_seen.isoformat() if obs.first_seen else "",
            obs.last_seen.isoformat() if obs.last_seen else "",
            obs.category or "",
            tags_str,
            sources_str,
            obs.description or "",
        ])

    return output.getvalue()


def _serialize_datetime(obj: Any) -> Any:
    """JSON serialization helper for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_json(observables: list[Observable]) -> str:
    """Export observables as a clean JSON array string."""
    items: list[dict[str, Any]] = []

    for obs in observables:
        # Extract tag names
        tag_names: list[str] = []
        tags = getattr(obs, "tags", None)
        if tags:
            for t in tags:
                if isinstance(t, str):
                    tag_names.append(t)
                elif hasattr(t, "name"):
                    tag_names.append(t.name)

        # Extract source/feed names
        source_names: list[str] = []
        sources = getattr(obs, "sources", None)
        if sources:
            for s in sources:
                if isinstance(s, str):
                    source_names.append(s)
                elif hasattr(s, "name"):
                    source_names.append(s.name)

        items.append({
            "id": str(obs.id),
            "type": obs.type.value if hasattr(obs.type, "value") else str(obs.type),
            "value": obs.value,
            "confidence_score": obs.confidence_score,
            "tlp": obs.tlp,
            "first_seen": obs.first_seen.isoformat() if obs.first_seen else None,
            "last_seen": obs.last_seen.isoformat() if obs.last_seen else None,
            "category": obs.category,
            "description": obs.description,
            "external_references": obs.external_references,
            "tags": tag_names,
            "sources": source_names,
        })

    return json.dumps(items, indent=2, default=_serialize_datetime)
