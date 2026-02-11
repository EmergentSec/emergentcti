"""REST API polling feed connector.

Supports configurable URL, HTTP headers, authentication (basic / bearer / API key),
pagination, and JSON field mapping for extracting observables from arbitrary REST APIs.

Feed config schema:
    {
        "headers": {"X-Custom": "value"},           # extra HTTP headers
        "auth_type": "bearer" | "basic" | "api_key",
        "method": "GET" | "POST",                   # HTTP method, default GET
        "request_body": {...},                       # optional POST body
        "results_path": "data.indicators",          # dot-path to results array
        "field_map": {                              # maps JSON fields -> observable fields
            "type": "indicator_type",
            "value": "indicator_value",
            "confidence_score": "confidence",
            "first_seen": "created",
            "last_seen": "updated",
            "tlp": "tlp_level",
            "context": "metadata"
        },
        "type_map": {                               # maps source types -> ObservableType values
            "IPv4": "ip-addr",
            "domain": "domain-name"
        },
        "default_type": "ip-addr",                  # fallback observable type
        "pagination": {
            "style": "page" | "offset" | "cursor",
            "page_param": "page",                   # query param name for page-based
            "page_size_param": "limit",
            "page_size": 100,
            "offset_param": "offset",               # for offset-based
            "cursor_param": "cursor",               # for cursor-based
            "cursor_path": "meta.next_cursor",      # dot-path to next cursor in response
            "total_path": "meta.total",             # dot-path to total count
            "max_pages": 50                          # safety limit
        }
    }

Auth config schema (encrypted):
    {
        "token": "bearer-token-here",           # for bearer auth
        "username": "user",                      # for basic auth
        "password": "pass",                      # for basic auth
        "api_key": "key-value",                  # for api_key auth
        "api_key_header": "X-API-Key"            # header name for api_key auth
    }
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from cti.core.config import get_settings
from cti.feeds.base import BaseFeedConnector
from cti.models.observable import ObservableType
from cti.schemas.observable import ObservableCreate


def _resolve_dot_path(data: Any, path: str) -> Any:
    """Traverse a nested dict/list using a dot-separated path.

    Example: _resolve_dot_path({"a": {"b": [1,2]}}, "a.b") -> [1, 2]
    """
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


class APIFeedConnector(BaseFeedConnector):
    """Feed connector for polling REST APIs."""

    def __init__(self, feed: Any) -> None:
        super().__init__(feed)
        settings = get_settings()
        self.timeout = self.config.get("timeout", settings.FEED_DEFAULT_TIMEOUT)
        self.method: str = self.config.get("method", "GET").upper()
        self.extra_headers: dict[str, str] = self.config.get("headers", {})
        self.results_path: str | None = self.config.get("results_path")
        self.field_map: dict[str, str] = self.config.get("field_map", {})
        self.type_map: dict[str, str] = self.config.get("type_map", {})
        self.default_type: str | None = self.config.get("default_type")
        self.pagination: dict[str, Any] = self.config.get("pagination", {})
        self.request_body: dict[str, Any] | None = self.config.get("request_body")
        self._client: httpx.AsyncClient | None = None

    def _build_auth_headers(self) -> dict[str, str]:
        """Build authentication headers from the decrypted auth config."""
        headers: dict[str, str] = {}
        auth_type = self.config.get("auth_type", "").lower()

        if auth_type == "bearer":
            token = self.auth_config.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            key_header = self.auth_config.get("api_key_header", "X-API-Key")
            key_value = self.auth_config.get("api_key", "")
            headers[key_header] = key_value
        # basic auth is handled via httpx auth parameter, not headers

        return headers

    def _build_basic_auth(self) -> httpx.BasicAuth | None:
        """Build httpx BasicAuth if auth_type is basic."""
        auth_type = self.config.get("auth_type", "").lower()
        if auth_type == "basic":
            username = self.auth_config.get("username", "")
            password = self.auth_config.get("password", "")
            return httpx.BasicAuth(username=username, password=password)
        return None

    async def connect(self) -> None:
        """Create the HTTP client and verify the endpoint is reachable."""
        headers = {**self.extra_headers, **self._build_auth_headers()}
        self._client = httpx.AsyncClient(
            headers=headers,
            auth=self._build_basic_auth(),
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
        )

        # Quick connectivity check with a HEAD request (fall back to GET for APIs
        # that don't support HEAD).
        if not self.url:
            raise ConnectionError("Feed URL is not configured")

        try:
            response = await self._client.head(self.url)
            # Accept any 2xx/3xx/405 (Method Not Allowed) as reachable
            if response.status_code >= 500:
                raise ConnectionError(
                    f"Server error during connectivity check: HTTP {response.status_code}"
                )
        except httpx.HTTPError as exc:
            raise ConnectionError(f"Cannot reach {self.url}: {exc}") from exc

    async def _fetch_page(
        self, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Fetch a single page of results."""
        if self._client is None:
            raise RuntimeError("Client not initialized; call connect() first")

        if self.method == "POST":
            body = {**(self.request_body or {}), **(params or {})}
            response = await self._client.post(url, json=body)
        else:
            response = await self._client.get(url, params=params)

        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch all pages of data from the API, handling pagination."""
        if not self.url:
            raise ValueError("Feed URL is not configured")

        all_records: list[dict[str, Any]] = []
        pagination_style = self.pagination.get("style")
        max_pages = int(self.pagination.get("max_pages", 50))

        if not pagination_style:
            # No pagination -- single request
            data = await self._fetch_page(self.url)
            records = self._extract_records(data)
            all_records.extend(records)
        elif pagination_style == "page":
            page_param = self.pagination.get("page_param", "page")
            size_param = self.pagination.get("page_size_param", "limit")
            page_size = int(self.pagination.get("page_size", 100))
            total_path = self.pagination.get("total_path")

            page = 1
            while page <= max_pages:
                params = {page_param: page, size_param: page_size}
                data = await self._fetch_page(self.url, params=params)
                records = self._extract_records(data)
                if not records:
                    break
                all_records.extend(records)

                # Check if we've fetched everything
                if total_path:
                    total = _resolve_dot_path(data, total_path)
                    if total is not None and len(all_records) >= int(total):
                        break

                if len(records) < page_size:
                    break
                page += 1

        elif pagination_style == "offset":
            offset_param = self.pagination.get("offset_param", "offset")
            size_param = self.pagination.get("page_size_param", "limit")
            page_size = int(self.pagination.get("page_size", 100))

            offset = 0
            pages_fetched = 0
            while pages_fetched < max_pages:
                params = {offset_param: offset, size_param: page_size}
                data = await self._fetch_page(self.url, params=params)
                records = self._extract_records(data)
                if not records:
                    break
                all_records.extend(records)
                if len(records) < page_size:
                    break
                offset += page_size
                pages_fetched += 1

        elif pagination_style == "cursor":
            cursor_param = self.pagination.get("cursor_param", "cursor")
            cursor_path = self.pagination.get("cursor_path", "meta.next_cursor")
            size_param = self.pagination.get("page_size_param", "limit")
            page_size = int(self.pagination.get("page_size", 100))

            cursor: str | None = None
            pages_fetched = 0
            while pages_fetched < max_pages:
                params: dict[str, Any] = {size_param: page_size}
                if cursor:
                    params[cursor_param] = cursor
                data = await self._fetch_page(self.url, params=params)
                records = self._extract_records(data)
                all_records.extend(records)

                next_cursor = _resolve_dot_path(data, cursor_path)
                if not next_cursor or not records:
                    break
                cursor = str(next_cursor)
                pages_fetched += 1
        else:
            raise ValueError(f"Unknown pagination style: {pagination_style}")

        self.logger.info("Fetched %d raw records from API", len(all_records))
        return all_records

    def _extract_records(self, data: Any) -> list[dict[str, Any]]:
        """Extract the list of records from the response using results_path."""
        if self.results_path:
            records = _resolve_dot_path(data, self.results_path)
        else:
            records = data

        if isinstance(records, list):
            return records  # type: ignore[return-value]
        if isinstance(records, dict):
            return [records]
        return []

    def _map_observable_type(self, raw_type: str | None) -> ObservableType | None:
        """Map a source-specific type string to an ObservableType enum value."""
        if raw_type and raw_type in self.type_map:
            mapped = self.type_map[raw_type]
        elif raw_type:
            mapped = raw_type
        elif self.default_type:
            mapped = self.default_type
        else:
            return None

        # Try matching by enum value (e.g. "ip-addr")
        for member in ObservableType:
            if member.value == mapped:
                return member
        # Try matching by enum name (e.g. "ip_addr")
        try:
            return ObservableType[mapped]
        except KeyError:
            return None

    def _get_field(self, record: dict[str, Any], observable_field: str) -> Any:
        """Get a value from a record using the configured field map."""
        source_field = self.field_map.get(observable_field, observable_field)
        return _resolve_dot_path(record, source_field)

    async def normalize(self, raw_data: list[dict[str, Any]]) -> list[ObservableCreate]:
        """Transform raw API records into ObservableCreate instances."""
        observables: list[ObservableCreate] = []

        for record in raw_data:
            try:
                raw_type = self._get_field(record, "type")
                obs_type = self._map_observable_type(str(raw_type) if raw_type else None)
                if obs_type is None:
                    self.logger.debug("Skipping record with unmappable type: %s", raw_type)
                    continue

                value = self._get_field(record, "value")
                if not value:
                    self.logger.debug("Skipping record with no value")
                    continue

                confidence = self._get_field(record, "confidence_score")
                first_seen = self._get_field(record, "first_seen")
                last_seen = self._get_field(record, "last_seen")
                tlp = self._get_field(record, "tlp")
                context = self._get_field(record, "context")

                kwargs: dict[str, Any] = {
                    "type": obs_type,
                    "value": str(value).strip(),
                }
                if confidence is not None:
                    kwargs["confidence_score"] = int(confidence)
                elif self.config.get("default_confidence") is not None:
                    kwargs["confidence_score"] = int(self.config["default_confidence"])
                if first_seen is not None:
                    kwargs["first_seen"] = (
                        first_seen
                        if isinstance(first_seen, datetime)
                        else datetime.fromisoformat(str(first_seen))
                    )
                if last_seen is not None:
                    kwargs["last_seen"] = (
                        last_seen
                        if isinstance(last_seen, datetime)
                        else datetime.fromisoformat(str(last_seen))
                    )
                if tlp is not None:
                    kwargs["tlp"] = str(tlp)
                if context is not None:
                    kwargs["context"] = context if isinstance(context, dict) else {"raw": context}

                observable = ObservableCreate(**kwargs)
                observables.append(observable)

            except Exception as exc:
                self.logger.warning("Failed to normalize record: %s — %s", record, exc)

        return observables

    async def __aenter__(self) -> "APIFeedConnector":
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
