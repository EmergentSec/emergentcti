"""TAXII 2.1 feed connector.

Uses taxii2-client for TAXII server discovery and collection polling, and stix2
for parsing STIX bundles. Maps STIX indicator patterns to internal observable
types via regex extraction.

Feed config schema:
    {
        "collection_id": "abc-123",               # TAXII collection ID (required)
        "added_after": "2024-01-01T00:00:00Z",    # filter: objects added after this timestamp
        "roots_index": 0,                          # index into api_roots list (default 0)
        "confidence_score": 70,                    # default confidence for all observables
        "tlp": "amber",                            # default TLP marking
        "stix_custom_properties": {                # extra STIX fields to include in context
            "x_mitre_id": true
        }
    }

Auth config schema (encrypted):
    {
        "username": "taxii-user",
        "password": "taxii-pass",
        "token": "bearer-token",        # alternative: use bearer token
        "cert_path": "/path/to/cert",   # alternative: client certificate
        "key_path": "/path/to/key"
    }
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx
from stix2 import parse as stix2_parse  # type: ignore[import-untyped]
from taxii2client.v21 import Collection, Server  # type: ignore[import-untyped]

from cti.core.config import get_settings
from cti.feeds.base import BaseFeedConnector
from cti.models.observable import ObservableType
from cti.schemas.observable import ObservableCreate

# Regex patterns to extract observables from STIX indicator patterns.
# STIX patterns look like: [ipv4-addr:value = '1.2.3.4']
STIX_PATTERN_MAP: list[tuple[re.Pattern[str], ObservableType]] = [
    (
        re.compile(r"\[ipv4-addr:value\s*=\s*'([^']+)'\]"),
        ObservableType.ip_addr,
    ),
    (
        re.compile(r"\[ipv6-addr:value\s*=\s*'([^']+)'\]"),
        ObservableType.ip_addr,
    ),
    (
        re.compile(r"\[domain-name:value\s*=\s*'([^']+)'\]"),
        ObservableType.domain_name,
    ),
    (
        re.compile(r"\[url:value\s*=\s*'([^']+)'\]"),
        ObservableType.url,
    ),
    (
        re.compile(r"\[email-addr:value\s*=\s*'([^']+)'\]"),
        ObservableType.email_addr,
    ),
    (
        re.compile(r"\[file:hashes\.'MD5'\s*=\s*'([^']+)'\]"),
        ObservableType.file_hash,
    ),
    (
        re.compile(r"\[file:hashes\.'SHA-1'\s*=\s*'([^']+)'\]"),
        ObservableType.file_hash,
    ),
    (
        re.compile(r"\[file:hashes\.'SHA-256'\s*=\s*'([^']+)'\]"),
        ObservableType.file_hash,
    ),
    (
        re.compile(r"\[file:hashes\.'SHA-512'\s*=\s*'([^']+)'\]"),
        ObservableType.file_hash,
    ),
    (
        re.compile(r"\[autonomous-system:number\s*=\s*(\d+)\]"),
        ObservableType.asn,
    ),
]

# Mapping of STIX Cyber Observable (SCO) types to our ObservableType.
SCO_TYPE_MAP: dict[str, ObservableType] = {
    "ipv4-addr": ObservableType.ip_addr,
    "ipv6-addr": ObservableType.ip_addr,
    "domain-name": ObservableType.domain_name,
    "url": ObservableType.url,
    "email-addr": ObservableType.email_addr,
    "file": ObservableType.file_hash,
    "autonomous-system": ObservableType.asn,
    "x509-certificate": ObservableType.certificate,
    "user-agent": ObservableType.user_agent,
}


class TAXIIFeedConnector(BaseFeedConnector):
    """Feed connector for TAXII 2.1 servers with STIX bundle parsing."""

    def __init__(self, feed: Any) -> None:
        super().__init__(feed)
        settings = get_settings()
        self.timeout = self.config.get("timeout", settings.FEED_DEFAULT_TIMEOUT)
        self.collection_id: str = self.config.get("collection_id", "")
        self.added_after: str | None = self.config.get("added_after")
        self.roots_index: int = int(self.config.get("roots_index", 0))
        self.default_confidence: int = int(self.config.get("confidence_score", 50))
        self.default_tlp: str = self.config.get("tlp", "clear")
        self.custom_props: dict[str, bool] = self.config.get("stix_custom_properties", {})
        self._collection: Collection | None = None

    def _build_taxii_auth(self) -> dict[str, Any]:
        """Build authentication kwargs for taxii2-client."""
        kwargs: dict[str, Any] = {}
        if self.auth_config.get("username"):
            kwargs["user"] = self.auth_config["username"]
            kwargs["password"] = self.auth_config.get("password", "")
        if self.auth_config.get("cert_path"):
            kwargs["cert"] = (
                self.auth_config["cert_path"],
                self.auth_config.get("key_path"),
            )
        return kwargs

    async def connect(self) -> None:
        """Discover the TAXII server and locate the target collection."""
        if not self.url:
            raise ConnectionError("TAXII server URL is not configured")

        if not self.collection_id:
            raise ConnectionError("TAXII collection_id is not configured")

        auth_kwargs = self._build_taxii_auth()

        # Verify the server is reachable with an async HTTP check first
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
            try:
                response = await client.get(self.url)
                if response.status_code >= 500:
                    raise ConnectionError(
                        f"TAXII server returned HTTP {response.status_code}"
                    )
            except httpx.HTTPError as exc:
                raise ConnectionError(f"Cannot reach TAXII server: {exc}") from exc

        # Use taxii2-client (synchronous) for TAXII discovery
        try:
            server = Server(self.url, **auth_kwargs)
            api_roots = server.api_roots

            if not api_roots:
                raise ConnectionError("No API roots found on TAXII server")

            if self.roots_index >= len(api_roots):
                raise ConnectionError(
                    f"API root index {self.roots_index} out of range "
                    f"(server has {len(api_roots)} roots)"
                )

            api_root = api_roots[self.roots_index]

            # Find the collection
            self._collection = None
            for collection in api_root.collections:
                if collection.id == self.collection_id:
                    self._collection = collection
                    break

            if self._collection is None:
                raise ConnectionError(
                    f"Collection {self.collection_id} not found on TAXII server"
                )

            self.logger.info(
                "Connected to TAXII collection: %s (%s)",
                self._collection.title,
                self._collection.id,
            )
        except ConnectionError:
            raise
        except Exception as exc:
            raise ConnectionError(f"TAXII discovery failed: {exc}") from exc

    async def fetch(self) -> dict[str, Any]:
        """Fetch STIX objects from the TAXII collection.

        Returns:
            The raw STIX bundle as a dict.
        """
        if self._collection is None:
            raise RuntimeError("Not connected; call connect() first")

        kwargs: dict[str, Any] = {}
        if self.added_after:
            kwargs["added_after"] = self.added_after

        # taxii2-client's get_objects is synchronous
        try:
            envelope = self._collection.get_objects(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch STIX objects: {exc}") from exc

        if isinstance(envelope, dict):
            return envelope

        # Some versions return a response object; extract the JSON
        if hasattr(envelope, "json"):
            return envelope.json()  # type: ignore[no-any-return]
        if hasattr(envelope, "response"):
            import json

            return json.loads(envelope.response.text)  # type: ignore[no-any-return]

        raise RuntimeError(f"Unexpected TAXII response type: {type(envelope)}")

    def _extract_from_indicator(
        self, indicator: Any
    ) -> list[tuple[ObservableType, str]]:
        """Extract observable type-value pairs from a STIX indicator pattern."""
        pattern = getattr(indicator, "pattern", "") or ""
        results: list[tuple[ObservableType, str]] = []

        for regex, obs_type in STIX_PATTERN_MAP:
            for match in regex.finditer(pattern):
                value = match.group(1)
                # Prefix ASN with "AS" if it's just a number
                if obs_type == ObservableType.asn and not value.upper().startswith("AS"):
                    value = f"AS{value}"
                results.append((obs_type, value))

        return results

    def _extract_from_sco(
        self, sco: Any
    ) -> list[tuple[ObservableType, str]]:
        """Extract observable type-value pairs from a STIX Cyber Observable."""
        sco_type = getattr(sco, "type", "")
        obs_type = SCO_TYPE_MAP.get(sco_type)
        if obs_type is None:
            return []

        results: list[tuple[ObservableType, str]] = []

        if sco_type in ("ipv4-addr", "ipv6-addr", "domain-name", "url", "email-addr"):
            value = getattr(sco, "value", None)
            if value:
                results.append((obs_type, str(value)))

        elif sco_type == "file":
            hashes = getattr(sco, "hashes", {}) or {}
            if isinstance(hashes, dict):
                for hash_value in hashes.values():
                    results.append((ObservableType.file_hash, str(hash_value)))

        elif sco_type == "autonomous-system":
            number = getattr(sco, "number", None)
            if number is not None:
                results.append((ObservableType.asn, f"AS{number}"))

        elif sco_type == "x509-certificate":
            # Use SHA-256 or SHA-1 fingerprint
            hashes = getattr(sco, "hashes", {}) or {}
            if isinstance(hashes, dict):
                for hash_value in hashes.values():
                    results.append((ObservableType.certificate, str(hash_value)))
            # Fallback to serial_number if no hashes
            serial = getattr(sco, "serial_number", None)
            if serial and not hashes:
                results.append((ObservableType.certificate, str(serial)))

        return results

    def _build_context(self, stix_obj: Any) -> dict[str, Any]:
        """Build context dict from a STIX object's metadata."""
        context: dict[str, Any] = {}

        for attr in ("name", "description", "labels", "external_references"):
            val = getattr(stix_obj, attr, None)
            if val is not None:
                if attr == "external_references":
                    context[attr] = [
                        {k: v for k, v in ref.items()} if hasattr(ref, "items") else str(ref)
                        for ref in val
                    ]
                else:
                    context[attr] = val

        # Include configured custom properties
        for prop, include in self.custom_props.items():
            if include:
                val = getattr(stix_obj, prop, None)
                if val is not None:
                    context[prop] = val

        return context if context else {}

    async def normalize(self, raw_data: dict[str, Any]) -> list[ObservableCreate]:
        """Parse a STIX bundle and extract observables."""
        observables: list[ObservableCreate] = []
        seen: set[tuple[str, str]] = set()

        objects_list = raw_data.get("objects", [])
        self.logger.info("Processing %d STIX objects", len(objects_list))

        for raw_obj in objects_list:
            try:
                stix_obj = stix2_parse(raw_obj, allow_custom=True)
            except Exception as exc:
                self.logger.debug("Failed to parse STIX object: %s", exc)
                # Fall back to dict-based processing
                stix_obj = raw_obj

            obj_type = (
                getattr(stix_obj, "type", None)
                if not isinstance(stix_obj, dict)
                else stix_obj.get("type", "")
            )

            pairs: list[tuple[ObservableType, str]] = []

            if obj_type == "indicator":
                pairs = self._extract_from_indicator(stix_obj)
            elif obj_type in SCO_TYPE_MAP:
                pairs = self._extract_from_sco(stix_obj)

            if not pairs:
                continue

            # Build context from the STIX object
            context = (
                self._build_context(stix_obj)
                if not isinstance(stix_obj, dict)
                else {k: v for k, v in stix_obj.items() if k not in ("type", "id", "spec_version")}
            )

            # Extract timestamps
            created = getattr(stix_obj, "created", None) if not isinstance(stix_obj, dict) else None
            modified = getattr(stix_obj, "modified", None) if not isinstance(stix_obj, dict) else None

            for obs_type, value in pairs:
                dedup_key = (obs_type.value, value)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                try:
                    kwargs: dict[str, Any] = {
                        "type": obs_type,
                        "value": value.strip(),
                        "confidence_score": self.default_confidence,
                        "tlp": self.default_tlp,
                    }
                    if context:
                        kwargs["context"] = context
                    if created and isinstance(created, datetime):
                        kwargs["first_seen"] = created
                    if modified and isinstance(modified, datetime):
                        kwargs["last_seen"] = modified

                    observable = ObservableCreate(**kwargs)
                    observables.append(observable)
                except Exception as exc:
                    self.logger.warning(
                        "Failed to create observable from STIX object: %s — %s",
                        value,
                        exc,
                    )

        return observables
