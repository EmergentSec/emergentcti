from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup

from cti.feeds.base import BaseFeedConnector, RawObservable
from cti.models.observable import ObservableType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IOC regex patterns
# ---------------------------------------------------------------------------

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"
)
_URL_RE = re.compile(r'https?://[^\s<>"]+')
_MD5_RE = re.compile(r"\b[a-fA-F0-9]{32}\b")
_SHA1_RE = re.compile(r"\b[a-fA-F0-9]{40}\b")
_SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Defanging replacements
_DEFANG_MAP = [
    ("hxxp://", "http://"),
    ("hxxps://", "https://"),
    ("hXXp://", "http://"),
    ("hXXps://", "https://"),
    ("[.]", "."),
    ("(dot)", "."),
    ("[dot]", "."),
    ("[:]", ":"),
    ("[at]", "@"),
    ("[@]", "@"),
]

# Common TLDs to reduce false positives on domain matching
_MIN_DOMAIN_PARTS = 2


def _refang(text: str) -> str:
    """Replace common defanged indicator patterns with their real equivalents."""
    for defanged, real in _DEFANG_MAP:
        text = text.replace(defanged, real)
    return text


def _is_valid_ipv4(ip: str) -> bool:
    """Validate that each octet of an IPv4 address is in 0-255."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        try:
            val = int(part)
            if val < 0 or val > 255:
                return False
        except ValueError:
            return False
    return True


def _is_likely_hash(value: str) -> bool:
    """Check if a hex string is likely a hash and not just a hex-looking word."""
    # Must contain at least some digits and some letters to look like a real hash
    has_digit = any(c.isdigit() for c in value)
    has_alpha = any(c.isalpha() for c in value)
    return has_digit and has_alpha


class ScraperFeedConnector(BaseFeedConnector):
    """Connector that scrapes HTML pages for IOCs using regex extraction.

    Used for feeds that publish threat data as web pages without a
    proper API or downloadable list format.
    """

    async def fetch(self) -> str | bytes | dict | list:
        """Fetch raw HTML from the target URL."""
        timeout = self.config.get("timeout", 30)
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            headers = self.config.get("headers", {})
            response = await client.get(self.url, headers=headers)
            response.raise_for_status()
            return response.text

    def normalize(self, raw_data: str | bytes | dict | list) -> list[RawObservable]:
        """Parse HTML and extract IOCs using regex patterns."""
        html = raw_data if isinstance(raw_data, str) else str(raw_data)

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # If CSS selectors are configured, narrow the scope
        selectors = self.config.get("selectors")
        if selectors:
            text_parts: list[str] = []
            for selector in selectors:
                for element in soup.select(selector):
                    text_parts.append(element.get_text(separator=" "))
            text = " ".join(text_parts)
        else:
            text = soup.get_text(separator=" ")

        # Refang defanged indicators
        text = _refang(text)

        # Extract all IOC types
        observables: list[RawObservable] = []
        seen: set[tuple[str, str]] = set()  # (type, value) dedup

        # Order matters: extract URLs first (they contain domains and IPs),
        # then hashes (longest first to avoid partial matches), then others.

        # URLs
        for match in _URL_RE.finditer(text):
            value = match.group().rstrip(".,;:)\"'")
            key = (ObservableType.URL.value, value)
            if key not in seen:
                seen.add(key)
                observables.append(
                    RawObservable(type=ObservableType.URL, value=value)
                )

        # SHA256 hashes (64 hex chars)
        for match in _SHA256_RE.finditer(text):
            value = match.group()
            if _is_likely_hash(value):
                key = (ObservableType.FILE_HASH.value, value)
                if key not in seen:
                    seen.add(key)
                    observables.append(
                        RawObservable(type=ObservableType.FILE_HASH, value=value.lower())
                    )

        # SHA1 hashes (40 hex chars) -- skip if already matched as part of SHA256
        for match in _SHA1_RE.finditer(text):
            value = match.group()
            if _is_likely_hash(value):
                key = (ObservableType.FILE_HASH.value, value)
                if key not in seen:
                    # Ensure it's not a substring of a SHA256 we already captured
                    lower_val = value.lower()
                    is_substring = any(
                        lower_val in obs.value
                        for obs in observables
                        if obs.type == ObservableType.FILE_HASH
                        and len(obs.value) == 64
                    )
                    if not is_substring:
                        seen.add(key)
                        observables.append(
                            RawObservable(
                                type=ObservableType.FILE_HASH, value=lower_val
                            )
                        )

        # MD5 hashes (32 hex chars) -- skip if already matched as part of longer hash
        for match in _MD5_RE.finditer(text):
            value = match.group()
            if _is_likely_hash(value):
                key = (ObservableType.FILE_HASH.value, value)
                if key not in seen:
                    lower_val = value.lower()
                    is_substring = any(
                        lower_val in obs.value
                        for obs in observables
                        if obs.type == ObservableType.FILE_HASH
                        and len(obs.value) > 32
                    )
                    if not is_substring:
                        seen.add(key)
                        observables.append(
                            RawObservable(
                                type=ObservableType.FILE_HASH, value=lower_val
                            )
                        )

        # Emails
        for match in _EMAIL_RE.finditer(text):
            value = match.group()
            key = (ObservableType.EMAIL_ADDR.value, value)
            if key not in seen:
                seen.add(key)
                observables.append(
                    RawObservable(type=ObservableType.EMAIL_ADDR, value=value.lower())
                )

        # IPv4 addresses (skip those already captured inside URLs)
        url_text = " ".join(
            obs.value for obs in observables if obs.type == ObservableType.URL
        )
        for match in _IPV4_RE.finditer(text):
            value = match.group()
            if not _is_valid_ipv4(value):
                continue
            key = (ObservableType.IP_ADDR.value, value)
            if key not in seen:
                seen.add(key)
                observables.append(
                    RawObservable(type=ObservableType.IP_ADDR, value=value)
                )

        # Domains (skip those already captured inside URLs or emails)
        for match in _DOMAIN_RE.finditer(text):
            value = match.group()
            # Must have at least 2 parts
            parts = value.split(".")
            if len(parts) < _MIN_DOMAIN_PARTS:
                continue
            # Skip common non-IOC TLDs and very short domains
            if len(value) < 4:
                continue
            key = (ObservableType.DOMAIN_NAME.value, value)
            if key not in seen:
                seen.add(key)
                observables.append(
                    RawObservable(
                        type=ObservableType.DOMAIN_NAME, value=value.lower()
                    )
                )

        logger.info(
            "ScraperFeed %s: extracted %d observables",
            self.url,
            len(observables),
        )
        return observables
