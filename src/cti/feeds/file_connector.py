from __future__ import annotations

import csv
import io
import logging
import re

import httpx

from cti.feeds.base import BaseFeedConnector, RawObservable
from cti.models.observable import ObservableType

logger = logging.getLogger(__name__)

# Regex patterns for hash type detection
_MD5_RE = re.compile(r"^[a-fA-F0-9]{32}$")
_SHA1_RE = re.compile(r"^[a-fA-F0-9]{40}$")
_SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def _detect_hash_type(value: str) -> bool:
    """Return True if value looks like a valid hash (MD5, SHA1, or SHA256)."""
    return bool(_MD5_RE.match(value) or _SHA1_RE.match(value) or _SHA256_RE.match(value))


def _is_valid_value(value: str) -> bool:
    """Basic sanity check: non-empty, reasonable length, no obvious junk."""
    if not value:
        return False
    if len(value) > 2048:
        return False
    # Reject values that are purely whitespace or control characters
    if not value.strip():
        return False
    return True


class FileFeedConnector(BaseFeedConnector):
    """Connector for plain-text list and CSV feeds.

    This is the workhorse connector -- most free threat intel feeds publish
    simple text files (one IOC per line) or basic CSV exports.
    """

    async def fetch(self) -> str | bytes | dict | list:
        """Fetch the feed content via HTTP GET."""
        timeout = self.config.get("timeout", 30)
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            headers = self.config.get("headers", {})
            response = await client.get(self.url, headers=headers)
            response.raise_for_status()
            return response.text

    def normalize(self, raw_data: str | bytes | dict | list) -> list[RawObservable]:
        """Parse text or CSV data into normalized observables."""
        text = raw_data if isinstance(raw_data, str) else str(raw_data)
        fmt = self.config.get("format", "text")

        if fmt == "csv":
            return self._parse_csv(text)
        return self._parse_text(text)

    # ------------------------------------------------------------------
    # Text parsing
    # ------------------------------------------------------------------

    def _parse_text(self, text: str) -> list[RawObservable]:
        """Parse a plain-text IOC list (one value per line)."""
        comment_char = self.config.get("comment_char", "#")
        default_type = self._resolve_default_type()
        observables: list[RawObservable] = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if comment_char and line.startswith(comment_char):
                continue
            if not _is_valid_value(line):
                continue

            obs_type = self._detect_type(line, default_type)
            if obs_type is None:
                logger.debug("Skipping unrecognised value: %s", line[:80])
                continue

            observables.append(RawObservable(type=obs_type, value=line))

        logger.info(
            "FileFeed %s: parsed %d observables from text",
            self.url,
            len(observables),
        )
        return observables

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _parse_csv(self, text: str) -> list[RawObservable]:
        """Parse a CSV feed using column mapping from config."""
        csv_config = self.config.get("csv", {})
        column_map: dict = csv_config.get("column_map", {"value": 0})
        has_header = csv_config.get("has_header", False)
        default_type = self._resolve_default_type()

        observables: list[RawObservable] = []
        reader = csv.reader(io.StringIO(text))

        for idx, row in enumerate(reader):
            # Skip header row if configured
            if has_header and idx == 0:
                continue
            if not row:
                continue

            # Extract value from mapped column
            value_col = column_map.get("value", 0)
            if isinstance(value_col, int) and value_col >= len(row):
                continue
            value = row[value_col].strip() if isinstance(value_col, int) else ""
            if not _is_valid_value(value):
                continue

            # Optional: extract type from a column
            obs_type = default_type
            if "type" in column_map:
                type_col = column_map["type"]
                if isinstance(type_col, int) and type_col < len(row):
                    raw_type = row[type_col].strip()
                    type_map = csv_config.get("type_map", {})
                    if raw_type in type_map:
                        obs_type = ObservableType(type_map[raw_type])
                    else:
                        # Try direct enum match
                        try:
                            obs_type = ObservableType(raw_type)
                        except ValueError:
                            obs_type = default_type

            # Optional: extract native confidence
            native_confidence: int | None = None
            if "native_confidence" in column_map:
                conf_col = column_map["native_confidence"]
                if isinstance(conf_col, int) and conf_col < len(row):
                    try:
                        native_confidence = int(row[conf_col].strip())
                    except (ValueError, TypeError):
                        pass

            if obs_type is None:
                obs_type = self._detect_type(value, default_type)
            if obs_type is None:
                continue

            observables.append(
                RawObservable(
                    type=obs_type,
                    value=value,
                    native_confidence=native_confidence,
                )
            )

        logger.info(
            "FileFeed %s: parsed %d observables from CSV",
            self.url,
            len(observables),
        )
        return observables

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_default_type(self) -> ObservableType | None:
        """Resolve the default observable type from config."""
        raw = self.config.get("default_type") or self.config.get("csv", {}).get(
            "default_type"
        )
        if raw is None:
            return None
        try:
            return ObservableType(raw)
        except ValueError:
            logger.warning("Unknown default_type %r in config", raw)
            return None

    def _detect_type(
        self, value: str, default_type: ObservableType | None
    ) -> ObservableType | None:
        """Auto-detect the observable type, with special handling for file hashes.

        If the default_type is file-hash, we verify the value looks like a
        valid hash (MD5/SHA1/SHA256).  Otherwise we trust the default_type.
        """
        if default_type == ObservableType.FILE_HASH:
            if _detect_hash_type(value):
                return ObservableType.FILE_HASH
            return None  # skip non-hash values when feed claims to be hashes
        return default_type
