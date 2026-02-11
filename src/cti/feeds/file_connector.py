"""File-based feed connector (CSV, JSON, STIX bundles).

Supports downloading files from a URL via httpx and parsing them into
observables. Three file formats are supported: CSV with column mapping,
JSON with JSONPath-style dot-path extraction, and STIX bundles.

Feed config schema:
    {
        "format": "csv" | "json" | "stix",       # file format (required)

        # CSV-specific options
        "csv": {
            "delimiter": ",",
            "has_header": true,
            "skip_rows": 0,                        # rows to skip before header
            "comment_char": "#",                   # lines starting with this are skipped
            "column_map": {                        # column index or header name -> field
                "type": 0,                         # or "indicator_type"
                "value": 1,                        # or "indicator"
                "confidence_score": 2,
                "tlp": 3
            },
            "type_map": {                          # maps source type strings -> ObservableType values
                "IPv4": "ip-addr",
                "Domain": "domain-name"
            },
            "default_type": "ip-addr"              # if no type column, assume this type
        },

        # JSON-specific options
        "json": {
            "results_path": "data.indicators",     # dot-path to the array of records
            "field_map": {                          # dot-path from each record -> observable field
                "type": "indicator_type",
                "value": "indicator_value",
                "confidence_score": "confidence",
                "first_seen": "first_seen",
                "last_seen": "last_seen",
                "tlp": "tlp"
            },
            "type_map": {
                "IPv4": "ip-addr"
            },
            "default_type": "ip-addr"
        },

        # STIX-specific options
        "stix": {
            "confidence_score": 70,
            "tlp": "amber"
        },

        "encoding": "utf-8",                      # file encoding
        "max_file_size_mb": 50                     # safety limit for downloads
    }

Auth config schema (encrypted):
    {
        "token": "bearer-token",
        "username": "user",
        "password": "pass",
        "api_key": "key",
        "api_key_header": "Authorization"
    }
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Any

import httpx
from stix2 import parse as stix2_parse  # type: ignore[import-untyped]

from cti.core.config import get_settings
from cti.feeds.base import BaseFeedConnector
from cti.models.observable import ObservableType
from cti.schemas.observable import ObservableCreate

# Maximum default file size in bytes (50 MB)
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024

# STIX pattern regexes (shared with TAXII connector logic)
STIX_PATTERN_REGEXES: list[tuple[re.Pattern[str], ObservableType]] = [
    (re.compile(r"\[ipv4-addr:value\s*=\s*'([^']+)'\]"), ObservableType.ip_addr),
    (re.compile(r"\[ipv6-addr:value\s*=\s*'([^']+)'\]"), ObservableType.ip_addr),
    (re.compile(r"\[domain-name:value\s*=\s*'([^']+)'\]"), ObservableType.domain_name),
    (re.compile(r"\[url:value\s*=\s*'([^']+)'\]"), ObservableType.url),
    (re.compile(r"\[email-addr:value\s*=\s*'([^']+)'\]"), ObservableType.email_addr),
    (re.compile(r"\[file:hashes\.'MD5'\s*=\s*'([^']+)'\]"), ObservableType.file_hash),
    (re.compile(r"\[file:hashes\.'SHA-1'\s*=\s*'([^']+)'\]"), ObservableType.file_hash),
    (re.compile(r"\[file:hashes\.'SHA-256'\s*=\s*'([^']+)'\]"), ObservableType.file_hash),
    (re.compile(r"\[file:hashes\.'SHA-512'\s*=\s*'([^']+)'\]"), ObservableType.file_hash),
    (re.compile(r"\[autonomous-system:number\s*=\s*(\d+)\]"), ObservableType.asn),
]

SCO_TYPE_MAP: dict[str, ObservableType] = {
    "ipv4-addr": ObservableType.ip_addr,
    "ipv6-addr": ObservableType.ip_addr,
    "domain-name": ObservableType.domain_name,
    "url": ObservableType.url,
    "email-addr": ObservableType.email_addr,
    "file": ObservableType.file_hash,
    "autonomous-system": ObservableType.asn,
    "x509-certificate": ObservableType.certificate,
}


def _resolve_dot_path(data: Any, path: str) -> Any:
    """Traverse a nested dict/list using a dot-separated path."""
    current = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and key.isdigit():
            idx = int(key)
            current = current[idx] if idx < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _resolve_observable_type(
    raw_type: str | None,
    type_map: dict[str, str],
    default_type: str | None,
) -> ObservableType | None:
    """Map a raw type string to ObservableType."""
    if raw_type and raw_type in type_map:
        mapped = type_map[raw_type]
    elif raw_type:
        mapped = raw_type
    elif default_type:
        mapped = default_type
    else:
        return None

    for member in ObservableType:
        if member.value == mapped:
            return member
    try:
        return ObservableType[mapped]
    except KeyError:
        return None


class FileFeedConnector(BaseFeedConnector):
    """Feed connector for CSV, JSON, and STIX bundle files."""

    def __init__(self, feed: Any) -> None:
        super().__init__(feed)
        settings = get_settings()
        self.timeout = self.config.get("timeout", settings.FEED_DEFAULT_TIMEOUT)
        self.file_format: str = self.config.get("format", "csv").lower()
        self.encoding: str = self.config.get("encoding", "utf-8")
        max_mb = self.config.get("max_file_size_mb", 50)
        self.max_file_size: int = int(max_mb) * 1024 * 1024
        self._client: httpx.AsyncClient | None = None

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers from auth config for file download."""
        headers: dict[str, str] = {}
        if self.auth_config.get("token"):
            headers["Authorization"] = f"Bearer {self.auth_config['token']}"
        elif self.auth_config.get("api_key"):
            header_name = self.auth_config.get("api_key_header", "Authorization")
            headers[header_name] = self.auth_config["api_key"]
        return headers

    def _build_basic_auth(self) -> httpx.BasicAuth | None:
        """Build httpx BasicAuth if credentials are present."""
        if self.auth_config.get("username"):
            return httpx.BasicAuth(
                username=self.auth_config["username"],
                password=self.auth_config.get("password", ""),
            )
        return None

    async def connect(self) -> None:
        """Validate the file URL is reachable."""
        if not self.url:
            raise ConnectionError("Feed URL is not configured")

        if self.file_format not in ("csv", "json", "stix"):
            raise ConnectionError(f"Unsupported file format: {self.file_format}")

        self._client = httpx.AsyncClient(
            headers=self._build_headers(),
            auth=self._build_basic_auth(),
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
        )

        try:
            response = await self._client.head(self.url)
            if response.status_code >= 500:
                raise ConnectionError(
                    f"Server error during connectivity check: HTTP {response.status_code}"
                )

            # Check Content-Length if available
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self.max_file_size:
                raise ConnectionError(
                    f"File too large: {int(content_length)} bytes "
                    f"(limit: {self.max_file_size} bytes)"
                )
        except httpx.HTTPError as exc:
            raise ConnectionError(f"Cannot reach {self.url}: {exc}") from exc

    async def fetch(self) -> bytes:
        """Download the file content from the URL.

        Returns:
            Raw file bytes.
        """
        if self._client is None:
            raise RuntimeError("Client not initialized; call connect() first")

        if not self.url:
            raise ValueError("Feed URL is not configured")

        response = await self._client.get(self.url)
        response.raise_for_status()

        content = response.content
        if len(content) > self.max_file_size:
            raise ValueError(
                f"Downloaded file exceeds size limit: {len(content)} bytes "
                f"(limit: {self.max_file_size} bytes)"
            )

        self.logger.info("Downloaded %d bytes from %s", len(content), self.url)
        return content

    async def normalize(self, raw_data: bytes) -> list[ObservableCreate]:
        """Parse the file content based on the configured format."""
        if self.file_format == "csv":
            return self._parse_csv(raw_data)
        elif self.file_format == "json":
            return self._parse_json(raw_data)
        elif self.file_format == "stix":
            return self._parse_stix(raw_data)
        else:
            raise ValueError(f"Unsupported file format: {self.file_format}")

    # ──────────────────────────────────────────────────────────
    # CSV parsing
    # ──────────────────────────────────────────────────────────

    def _parse_csv(self, raw_data: bytes) -> list[ObservableCreate]:
        """Parse CSV content into observables."""
        csv_config = self.config.get("csv", {})
        delimiter = csv_config.get("delimiter", ",")
        has_header = csv_config.get("has_header", True)
        skip_rows = int(csv_config.get("skip_rows", 0))
        comment_char = csv_config.get("comment_char", "#")
        column_map: dict[str, str | int] = csv_config.get("column_map", {})
        type_map: dict[str, str] = csv_config.get("type_map", {})
        default_type: str | None = csv_config.get("default_type")

        text = raw_data.decode(self.encoding)
        lines = text.splitlines()

        # Skip leading rows
        lines = lines[skip_rows:]

        # Remove comment lines
        if comment_char:
            lines = [line for line in lines if not line.strip().startswith(comment_char)]

        if not lines:
            return []

        reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return []

        # Build column index mapping
        header: list[str] = []
        data_rows = rows
        if has_header:
            header = [h.strip() for h in rows[0]]
            data_rows = rows[1:]

        def _col_index(col_ref: str | int) -> int | None:
            """Resolve a column reference (int index or header name) to an index."""
            if isinstance(col_ref, int):
                return col_ref
            if isinstance(col_ref, str) and col_ref.isdigit():
                return int(col_ref)
            if header:
                try:
                    return header.index(col_ref)
                except ValueError:
                    return None
            return None

        type_idx = _col_index(column_map.get("type", "type"))  # type: ignore[arg-type]
        value_idx = _col_index(column_map.get("value", "value"))  # type: ignore[arg-type]
        confidence_idx = _col_index(column_map.get("confidence_score", "confidence_score"))  # type: ignore[arg-type]
        tlp_idx = _col_index(column_map.get("tlp", "tlp"))  # type: ignore[arg-type]
        first_seen_idx = _col_index(column_map.get("first_seen", "first_seen"))  # type: ignore[arg-type]
        last_seen_idx = _col_index(column_map.get("last_seen", "last_seen"))  # type: ignore[arg-type]

        if value_idx is None:
            # If no value column is configured, try index 0 as fallback
            # (common for simple IOC lists with one value per line)
            value_idx = 0

        observables: list[ObservableCreate] = []

        for row in data_rows:
            if not row or all(cell.strip() == "" for cell in row):
                continue

            try:
                # Extract value
                if value_idx >= len(row):
                    continue
                value = row[value_idx].strip()
                if not value:
                    continue

                # Extract type
                raw_type: str | None = None
                if type_idx is not None and type_idx < len(row):
                    raw_type = row[type_idx].strip() or None

                obs_type = _resolve_observable_type(raw_type, type_map, default_type)
                if obs_type is None:
                    self.logger.debug("Skipping row with unmappable type: %s", raw_type)
                    continue

                kwargs: dict[str, Any] = {"type": obs_type, "value": value}

                if confidence_idx is not None and confidence_idx < len(row):
                    try:
                        kwargs["confidence_score"] = int(row[confidence_idx].strip())
                    except (ValueError, IndexError):
                        pass

                if "confidence_score" not in kwargs:
                    csv_default = csv_config.get("default_confidence")
                    global_default = self.config.get("default_confidence")
                    if csv_default is not None:
                        kwargs["confidence_score"] = int(csv_default)
                    elif global_default is not None:
                        kwargs["confidence_score"] = int(global_default)

                if tlp_idx is not None and tlp_idx < len(row):
                    tlp_val = row[tlp_idx].strip()
                    if tlp_val:
                        kwargs["tlp"] = tlp_val

                if first_seen_idx is not None and first_seen_idx < len(row):
                    try:
                        kwargs["first_seen"] = datetime.fromisoformat(row[first_seen_idx].strip())
                    except (ValueError, IndexError):
                        pass

                if last_seen_idx is not None and last_seen_idx < len(row):
                    try:
                        kwargs["last_seen"] = datetime.fromisoformat(row[last_seen_idx].strip())
                    except (ValueError, IndexError):
                        pass

                observable = ObservableCreate(**kwargs)
                observables.append(observable)

            except Exception as exc:
                self.logger.warning("Failed to parse CSV row %s: %s", row, exc)

        return observables

    # ──────────────────────────────────────────────────────────
    # JSON parsing
    # ──────────────────────────────────────────────────────────

    def _parse_json(self, raw_data: bytes) -> list[ObservableCreate]:
        """Parse JSON content into observables."""
        json_config = self.config.get("json", {})
        results_path: str | None = json_config.get("results_path")
        field_map: dict[str, str] = json_config.get("field_map", {})
        type_map: dict[str, str] = json_config.get("type_map", {})
        default_type: str | None = json_config.get("default_type")

        text = raw_data.decode(self.encoding)
        data = json.loads(text)

        # Extract the array of records
        if results_path:
            records = _resolve_dot_path(data, results_path)
        else:
            records = data

        if not isinstance(records, list):
            if isinstance(records, dict):
                records = [records]
            else:
                self.logger.warning("JSON data is not a list or dict; got %s", type(records))
                return []

        observables: list[ObservableCreate] = []

        for record in records:
            if not isinstance(record, dict):
                continue

            try:
                # Resolve fields through field_map
                def _get(field_name: str) -> Any:
                    source = field_map.get(field_name, field_name)
                    return _resolve_dot_path(record, source)

                raw_type = _get("type")
                obs_type = _resolve_observable_type(
                    str(raw_type) if raw_type else None, type_map, default_type
                )
                if obs_type is None:
                    continue

                value = _get("value")
                if not value:
                    continue

                kwargs: dict[str, Any] = {
                    "type": obs_type,
                    "value": str(value).strip(),
                }

                confidence = _get("confidence_score")
                if confidence is not None:
                    kwargs["confidence_score"] = int(confidence)
                else:
                    json_default = json_config.get("default_confidence")
                    global_default = self.config.get("default_confidence")
                    if json_default is not None:
                        kwargs["confidence_score"] = int(json_default)
                    elif global_default is not None:
                        kwargs["confidence_score"] = int(global_default)

                first_seen = _get("first_seen")
                if first_seen is not None:
                    kwargs["first_seen"] = (
                        first_seen
                        if isinstance(first_seen, datetime)
                        else datetime.fromisoformat(str(first_seen))
                    )

                last_seen = _get("last_seen")
                if last_seen is not None:
                    kwargs["last_seen"] = (
                        last_seen
                        if isinstance(last_seen, datetime)
                        else datetime.fromisoformat(str(last_seen))
                    )

                tlp = _get("tlp")
                if tlp is not None:
                    kwargs["tlp"] = str(tlp)

                context = _get("context")
                if context is not None:
                    kwargs["context"] = context if isinstance(context, dict) else {"raw": context}

                observable = ObservableCreate(**kwargs)
                observables.append(observable)

            except Exception as exc:
                self.logger.warning("Failed to parse JSON record: %s — %s", record, exc)

        return observables

    # ──────────────────────────────────────────────────────────
    # STIX bundle parsing
    # ──────────────────────────────────────────────────────────

    def _parse_stix(self, raw_data: bytes) -> list[ObservableCreate]:
        """Parse a STIX bundle file into observables."""
        stix_config = self.config.get("stix", {})
        default_confidence = int(
            stix_config.get("confidence_score")
            or self.config.get("default_confidence")
            or 50
        )
        default_tlp = stix_config.get("tlp", "clear")

        text = raw_data.decode(self.encoding)
        bundle = json.loads(text)

        if not isinstance(bundle, dict) or "objects" not in bundle:
            self.logger.warning("STIX bundle missing 'objects' key")
            return []

        observables: list[ObservableCreate] = []
        seen: set[tuple[str, str]] = set()

        for raw_obj in bundle["objects"]:
            try:
                stix_obj = stix2_parse(raw_obj, allow_custom=True)
            except Exception:
                stix_obj = raw_obj

            obj_type = (
                getattr(stix_obj, "type", "")
                if not isinstance(stix_obj, dict)
                else stix_obj.get("type", "")
            )

            pairs: list[tuple[ObservableType, str]] = []

            if obj_type == "indicator":
                pattern = (
                    getattr(stix_obj, "pattern", "")
                    if not isinstance(stix_obj, dict)
                    else stix_obj.get("pattern", "")
                )
                for regex, obs_type in STIX_PATTERN_REGEXES:
                    for match in regex.finditer(pattern or ""):
                        value = match.group(1)
                        if obs_type == ObservableType.asn and not value.upper().startswith("AS"):
                            value = f"AS{value}"
                        pairs.append((obs_type, value))

            elif obj_type in SCO_TYPE_MAP:
                pairs = self._extract_sco_values(stix_obj, obj_type)

            # Build context
            context: dict[str, Any] = {}
            for attr in ("name", "description", "labels"):
                val = (
                    getattr(stix_obj, attr, None)
                    if not isinstance(stix_obj, dict)
                    else stix_obj.get(attr)
                )
                if val is not None:
                    context[attr] = val

            # Extract timestamps
            created = (
                getattr(stix_obj, "created", None)
                if not isinstance(stix_obj, dict)
                else None
            )
            modified = (
                getattr(stix_obj, "modified", None)
                if not isinstance(stix_obj, dict)
                else None
            )

            for obs_type, value in pairs:
                dedup_key = (obs_type.value, value)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                try:
                    kwargs: dict[str, Any] = {
                        "type": obs_type,
                        "value": value.strip(),
                        "confidence_score": default_confidence,
                        "tlp": default_tlp,
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
                        "Failed to create observable from STIX file: %s — %s", value, exc
                    )

        return observables

    def _extract_sco_values(
        self, sco: Any, sco_type: str
    ) -> list[tuple[ObservableType, str]]:
        """Extract observable pairs from a STIX Cyber Observable object."""
        obs_type = SCO_TYPE_MAP.get(sco_type)
        if obs_type is None:
            return []

        results: list[tuple[ObservableType, str]] = []
        is_dict = isinstance(sco, dict)

        if sco_type in ("ipv4-addr", "ipv6-addr", "domain-name", "url", "email-addr"):
            value = sco.get("value") if is_dict else getattr(sco, "value", None)
            if value:
                results.append((obs_type, str(value)))

        elif sco_type == "file":
            hashes = sco.get("hashes", {}) if is_dict else getattr(sco, "hashes", {})
            if isinstance(hashes, dict):
                for hash_value in hashes.values():
                    results.append((ObservableType.file_hash, str(hash_value)))

        elif sco_type == "autonomous-system":
            number = sco.get("number") if is_dict else getattr(sco, "number", None)
            if number is not None:
                results.append((ObservableType.asn, f"AS{number}"))

        elif sco_type == "x509-certificate":
            hashes = sco.get("hashes", {}) if is_dict else getattr(sco, "hashes", {})
            if isinstance(hashes, dict):
                for hash_value in hashes.values():
                    results.append((ObservableType.certificate, str(hash_value)))

        return results

    async def __aenter__(self) -> "FileFeedConnector":
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
