"""Web scraper feed connector.

Uses BeautifulSoup with lxml for HTML parsing and CSS selectors for targeted
extraction. Includes regex-based IOC extraction patterns for automatically
identifying IPs, domains, hashes, URLs, and email addresses in unstructured text.

Feed config schema:
    {
        "selectors": [                              # CSS selectors to extract text blocks
            "article.content",
            "div.ioc-list",
            "pre",
            "table.indicators tbody tr"
        ],
        "extract_from": "text" | "html",            # extract from element text or inner HTML
        "ioc_patterns": {                           # override default extraction patterns
            "ip_addr": true,                        # enable/disable each type
            "domain_name": true,
            "file_hash": true,
            "url": true,
            "email_addr": true
        },
        "defang": true,                             # re-fang defanged IOCs (hXXp, [.], etc.)
        "confidence_score": 40,                     # default confidence (lower for scraped)
        "tlp": "clear",
        "exclude_patterns": [                       # regex patterns for values to exclude
            "example\\.com$",
            "^10\\.",
            "^192\\.168\\."
        ],
        "table_mode": {                             # optional: structured table extraction
            "enabled": false,
            "type_column": 0,                       # column index for type
            "value_column": 1,                      # column index for value
            "type_map": {
                "IPv4": "ip-addr"
            }
        },
        "follow_links": false,                      # follow links on the page (single depth)
        "link_selector": "a.ioc-link",             # CSS selector for links to follow
        "max_links": 10                             # max links to follow
    }

Auth config schema (encrypted):
    {
        "token": "bearer-token",
        "cookies": {"session": "abc123"},
        "username": "user",
        "password": "pass"
    }
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from cti.core.config import get_settings
from cti.feeds.base import BaseFeedConnector
from cti.models.observable import ObservableType
from cti.schemas.observable import ObservableCreate

# ──────────────────────────────────────────────────────────
# IOC extraction regex patterns
# ──────────────────────────────────────────────────────────

# IPv4 address (standard dotted notation, also matches defanged with [.])
IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?:\[\.\]|\.))"
    r"{3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

# IPv6 address (simplified pattern for common formats)
IPV6_PATTERN = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"
    r"|\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b"
    r"|\b(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}\b"
    r"|\b::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}\b"
)

# Domain name (supports defanged [.] notation)
DOMAIN_PATTERN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?"
    r"(?:\[\.\]|\.))"
    r"+(?:[a-zA-Z]{2,})\b"
)

# URL (supports defanged hXXp, hxxps, [://], [.])
URL_PATTERN = re.compile(
    r"(?:h[Xx][Xx]ps?|https?)"
    r"(?::\/\/|\[:\/{2}\])"
    r"[^\s<>\"'\\]{3,}"
)

# File hashes (MD5, SHA-1, SHA-256, SHA-512)
MD5_PATTERN = re.compile(r"\b[0-9a-fA-F]{32}\b")
SHA1_PATTERN = re.compile(r"\b[0-9a-fA-F]{40}\b")
SHA256_PATTERN = re.compile(r"\b[0-9a-fA-F]{64}\b")
SHA512_PATTERN = re.compile(r"\b[0-9a-fA-F]{128}\b")

# Email address (supports defanged [@] and [.])
EMAIL_PATTERN = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+(?:@|\[@\]|\[at\])"
    r"[a-zA-Z0-9.\-]+(?:\[\.\]|\.)[a-zA-Z]{2,}\b",
    re.IGNORECASE,
)

# Defanging reversal patterns
DEFANG_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\[\.\]"), "."),
    (re.compile(r"\[:\/{2}\]"), "://"),
    (re.compile(r"\[@\]", re.IGNORECASE), "@"),
    (re.compile(r"\[at\]", re.IGNORECASE), "@"),
    (re.compile(r"hXXps?", re.IGNORECASE), lambda m: m.group(0).lower().replace("xx", "tt")),  # type: ignore[list-item]
]


def _refang(value: str) -> str:
    """Convert defanged IOC notation back to standard form."""
    result = value
    for pattern, replacement in DEFANG_REPLACEMENTS:
        if callable(replacement):
            result = pattern.sub(replacement, result)
        else:
            result = pattern.sub(replacement, result)
    return result


class ScraperFeedConnector(BaseFeedConnector):
    """Feed connector for scraping web pages for IOCs."""

    def __init__(self, feed: Any) -> None:
        super().__init__(feed)
        settings = get_settings()
        self.timeout = self.config.get("timeout", settings.FEED_DEFAULT_TIMEOUT)
        self.selectors: list[str] = self.config.get("selectors", [])
        self.extract_from: str = self.config.get("extract_from", "text")
        self.defang: bool = self.config.get("defang", True)
        self.default_confidence: int = int(self.config.get("confidence_score", 40))
        self.default_tlp: str = self.config.get("tlp", "clear")
        self.follow_links: bool = self.config.get("follow_links", False)
        self.link_selector: str = self.config.get("link_selector", "a")
        self.max_links: int = int(self.config.get("max_links", 10))

        # IOC pattern toggles
        ioc_config = self.config.get("ioc_patterns", {})
        self.extract_ips: bool = ioc_config.get("ip_addr", True)
        self.extract_domains: bool = ioc_config.get("domain_name", True)
        self.extract_hashes: bool = ioc_config.get("file_hash", True)
        self.extract_urls: bool = ioc_config.get("url", True)
        self.extract_emails: bool = ioc_config.get("email_addr", True)

        # Exclusion patterns
        raw_exclude = self.config.get("exclude_patterns", [])
        self.exclude_patterns: list[re.Pattern[str]] = [
            re.compile(p) for p in raw_exclude
        ]

        # Table mode config
        self.table_mode: dict[str, Any] = self.config.get("table_mode", {})

        self._client: httpx.AsyncClient | None = None

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for requests."""
        headers: dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if self.auth_config.get("token"):
            headers["Authorization"] = f"Bearer {self.auth_config['token']}"
        return headers

    async def connect(self) -> None:
        """Create the HTTP client and verify the page is reachable."""
        if not self.url:
            raise ConnectionError("Feed URL is not configured")

        cookies = self.auth_config.get("cookies")
        auth = None
        if self.auth_config.get("username"):
            auth = httpx.BasicAuth(
                username=self.auth_config["username"],
                password=self.auth_config.get("password", ""),
            )

        self._client = httpx.AsyncClient(
            headers=self._build_headers(),
            cookies=cookies,
            auth=auth,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
        )

        try:
            response = await self._client.get(self.url)
            if response.status_code >= 400:
                raise ConnectionError(
                    f"Page returned HTTP {response.status_code}: {self.url}"
                )
        except httpx.HTTPError as exc:
            raise ConnectionError(f"Cannot reach {self.url}: {exc}") from exc

    async def fetch(self) -> list[str]:
        """Fetch the web page(s) and return the HTML content(s).

        Returns:
            A list of HTML strings (one per page fetched).
        """
        if self._client is None:
            raise RuntimeError("Client not initialized; call connect() first")
        if not self.url:
            raise ValueError("Feed URL is not configured")

        pages: list[str] = []

        # Fetch the main page
        response = await self._client.get(self.url)
        response.raise_for_status()
        main_html = response.text
        pages.append(main_html)

        # Optionally follow links on the page
        if self.follow_links and self.link_selector:
            soup = BeautifulSoup(main_html, "lxml")
            link_elements = soup.select(self.link_selector)
            links_followed = 0

            for element in link_elements:
                if links_followed >= self.max_links:
                    break

                href = element.get("href") if isinstance(element, Tag) else None
                if not href or not isinstance(href, str):
                    continue

                # Resolve relative URLs
                if href.startswith("/"):
                    from urllib.parse import urlparse

                    parsed = urlparse(self.url)
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                elif not href.startswith(("http://", "https://")):
                    continue

                try:
                    sub_response = await self._client.get(href)
                    if sub_response.status_code == 200:
                        pages.append(sub_response.text)
                        links_followed += 1
                except httpx.HTTPError as exc:
                    self.logger.debug("Failed to follow link %s: %s", href, exc)

        self.logger.info("Fetched %d page(s) for scraping", len(pages))
        return pages

    def _is_excluded(self, value: str) -> bool:
        """Check if a value matches any exclusion pattern."""
        return any(pattern.search(value) for pattern in self.exclude_patterns)

    def _extract_iocs_from_text(self, text: str) -> list[tuple[ObservableType, str]]:
        """Extract IOCs from a text block using regex patterns."""
        results: list[tuple[ObservableType, str]] = []

        if self.extract_urls:
            for match in URL_PATTERN.finditer(text):
                value = match.group(0)
                if self.defang:
                    value = _refang(value)
                if not self._is_excluded(value):
                    results.append((ObservableType.url, value))

        if self.extract_emails:
            for match in EMAIL_PATTERN.finditer(text):
                value = match.group(0)
                if self.defang:
                    value = _refang(value)
                if not self._is_excluded(value):
                    results.append((ObservableType.email_addr, value))

        if self.extract_hashes:
            # Check longest hashes first to avoid substring matches
            for match in SHA512_PATTERN.finditer(text):
                value = match.group(0).lower()
                if not self._is_excluded(value):
                    results.append((ObservableType.file_hash, value))

            # Mark positions already matched by longer hashes to avoid duplicates
            matched_positions: set[tuple[int, int]] = set()
            for match in SHA512_PATTERN.finditer(text):
                matched_positions.add((match.start(), match.end()))

            for match in SHA256_PATTERN.finditer(text):
                pos = (match.start(), match.end())
                if not any(s <= pos[0] and e >= pos[1] for s, e in matched_positions):
                    value = match.group(0).lower()
                    if not self._is_excluded(value):
                        results.append((ObservableType.file_hash, value))
                    matched_positions.add(pos)

            for match in SHA1_PATTERN.finditer(text):
                pos = (match.start(), match.end())
                if not any(s <= pos[0] and e >= pos[1] for s, e in matched_positions):
                    value = match.group(0).lower()
                    if not self._is_excluded(value):
                        results.append((ObservableType.file_hash, value))
                    matched_positions.add(pos)

            for match in MD5_PATTERN.finditer(text):
                pos = (match.start(), match.end())
                if not any(s <= pos[0] and e >= pos[1] for s, e in matched_positions):
                    value = match.group(0).lower()
                    if not self._is_excluded(value):
                        results.append((ObservableType.file_hash, value))
                    matched_positions.add(pos)

        if self.extract_ips:
            for match in IPV4_PATTERN.finditer(text):
                value = match.group(0)
                if self.defang:
                    value = _refang(value)
                if not self._is_excluded(value):
                    results.append((ObservableType.ip_addr, value))

            for match in IPV6_PATTERN.finditer(text):
                value = match.group(0)
                if not self._is_excluded(value):
                    results.append((ObservableType.ip_addr, value))

        if self.extract_domains:
            # Extract domains, but filter out things that look like they're
            # part of a URL (already captured) or an email (already captured)
            for match in DOMAIN_PATTERN.finditer(text):
                value = match.group(0)
                if self.defang:
                    value = _refang(value)
                if not self._is_excluded(value):
                    results.append((ObservableType.domain_name, value))

        return results

    def _extract_from_table(
        self, soup: BeautifulSoup
    ) -> list[tuple[ObservableType, str]]:
        """Extract IOCs from HTML tables using structured column mapping."""
        if not self.table_mode.get("enabled"):
            return []

        type_col = int(self.table_mode.get("type_column", 0))
        value_col = int(self.table_mode.get("value_column", 1))
        type_map: dict[str, str] = self.table_mode.get("type_map", {})

        results: list[tuple[ObservableType, str]] = []

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) <= max(type_col, value_col):
                    continue

                raw_type = cells[type_col].get_text(strip=True)
                value = cells[value_col].get_text(strip=True)

                if not value:
                    continue

                # Map type
                mapped = type_map.get(raw_type, raw_type)
                obs_type: ObservableType | None = None
                for member in ObservableType:
                    if member.value == mapped:
                        obs_type = member
                        break
                if obs_type is None:
                    try:
                        obs_type = ObservableType[mapped]
                    except KeyError:
                        continue

                if not self._is_excluded(value):
                    results.append((obs_type, value))

        return results

    async def normalize(self, raw_data: list[str]) -> list[ObservableCreate]:
        """Extract IOCs from HTML pages and create observables."""
        all_pairs: list[tuple[ObservableType, str]] = []

        for html in raw_data:
            soup = BeautifulSoup(html, "lxml")

            # Table-mode extraction (structured)
            table_pairs = self._extract_from_table(soup)
            all_pairs.extend(table_pairs)

            # CSS-selector-based extraction
            if self.selectors:
                for selector in self.selectors:
                    elements = soup.select(selector)
                    for element in elements:
                        if self.extract_from == "html":
                            text = str(element)
                        else:
                            text = element.get_text(separator=" ")
                        pairs = self._extract_iocs_from_text(text)
                        all_pairs.extend(pairs)
            else:
                # No selectors configured: extract from the entire page body
                body = soup.find("body")
                if body:
                    text = body.get_text(separator=" ") if isinstance(body, Tag) else str(body)
                else:
                    text = soup.get_text(separator=" ")
                pairs = self._extract_iocs_from_text(text)
                all_pairs.extend(pairs)

        # Deduplicate by (type, value)
        seen: set[tuple[str, str]] = set()
        observables: list[ObservableCreate] = []

        for obs_type, value in all_pairs:
            clean_value = value.strip()
            dedup_key = (obs_type.value, clean_value)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            try:
                observable = ObservableCreate(
                    type=obs_type,
                    value=clean_value,
                    confidence_score=self.default_confidence,
                    tlp=self.default_tlp,
                    context={"source_url": self.url, "extraction_method": "scraper"},
                )
                observables.append(observable)
            except Exception as exc:
                self.logger.warning(
                    "Failed to create observable from scraped value '%s': %s",
                    clean_value,
                    exc,
                )

        return observables

    async def __aenter__(self) -> "ScraperFeedConnector":
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
