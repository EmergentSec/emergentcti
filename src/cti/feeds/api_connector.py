from __future__ import annotations

import logging
from typing import Any

import httpx

from cti.feeds.base import BaseFeedConnector, RawObservable
from cti.models.observable import ObservableType

logger = logging.getLogger(__name__)


def _resolve_path(data: Any, path: str) -> Any:
    """Walk a dot-notation path into a nested dict/list structure.

    Example: _resolve_path({"data": [1, 2]}, "data") -> [1, 2]
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _extract_field(item: dict, field_path: str) -> Any:
    """Extract a value from a dict using a dot-notation field path."""
    return _resolve_path(item, field_path)


class APIFeedConnector(BaseFeedConnector):
    """Connector for REST API feeds (JSON responses).

    Supports AbuseIPDB, AlienVault OTX, ThreatFox, GreyNoise, urlscan.io,
    PhishTank, and any other JSON API that follows similar patterns.
    """

    async def fetch(self) -> str | bytes | dict | list:
        """Fetch JSON data from the API, with optional pagination."""
        timeout = self.config.get("timeout", 30)
        method = self.config.get("method", "GET").upper()

        headers = dict(self.config.get("headers", {}))
        params = dict(self.config.get("params", {}))

        # Apply authentication
        self._apply_auth(headers)

        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            pagination = self.config.get("pagination")
            if pagination:
                return await self._fetch_paginated(
                    client, method, headers, params, pagination
                )
            return await self._fetch_single(client, method, headers, params)

    async def _fetch_single(
        self,
        client: httpx.AsyncClient,
        method: str,
        headers: dict,
        params: dict,
    ) -> dict | list:
        """Make a single HTTP request and return parsed JSON."""
        if method == "POST":
            body = self.config.get("request_body", {})
            response = await client.post(
                self.url, json=body, headers=headers, params=params
            )
        else:
            response = await client.get(self.url, headers=headers, params=params)

        response.raise_for_status()
        return response.json()

    async def _fetch_paginated(
        self,
        client: httpx.AsyncClient,
        method: str,
        headers: dict,
        params: dict,
        pagination: dict,
    ) -> list:
        """Fetch multiple pages and return combined results."""
        style = pagination.get("style", "page")
        page_param = pagination.get("page_param", "page")
        page_size = pagination.get("page_size", 100)
        max_pages = pagination.get("max_pages", 10)
        size_param = pagination.get("size_param")

        all_results: list = []

        for page_num in range(1, max_pages + 1):
            page_params = dict(params)
            if style == "offset":
                page_params[page_param] = (page_num - 1) * page_size
            else:
                page_params[page_param] = page_num

            if size_param:
                page_params[size_param] = page_size

            if method == "POST":
                body = self.config.get("request_body", {})
                response = await client.post(
                    self.url, json=body, headers=headers, params=page_params
                )
            else:
                response = await client.get(
                    self.url, headers=headers, params=page_params
                )

            response.raise_for_status()
            data = response.json()

            # Extract results using results_path
            results_path = self.config.get("results_path")
            if results_path:
                page_results = _resolve_path(data, results_path)
            else:
                page_results = data if isinstance(data, list) else [data]

            if not page_results:
                break  # No more results

            if isinstance(page_results, list):
                all_results.extend(page_results)
            else:
                all_results.append(page_results)

            # Stop if we got fewer results than page_size
            if isinstance(page_results, list) and len(page_results) < page_size:
                break

        return all_results

    def normalize(self, raw_data: str | bytes | dict | list) -> list[RawObservable]:
        """Transform the JSON response into normalized observables."""
        # Extract the results list from the response
        results_path = self.config.get("results_path")

        if results_path and isinstance(raw_data, dict):
            items = _resolve_path(raw_data, results_path)
        elif isinstance(raw_data, list):
            items = raw_data
        elif isinstance(raw_data, dict):
            items = [raw_data]
        else:
            logger.warning("Unexpected raw_data type: %s", type(raw_data))
            return []

        if items is None:
            logger.warning("results_path %r returned None", results_path)
            return []

        if not isinstance(items, list):
            items = [items]

        field_map: dict = self.config.get("field_map", {})
        type_map: dict = self.config.get("type_map", {})
        default_type_raw: str | None = self.config.get("default_type")

        observables: list[RawObservable] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            obs = self._map_item(item, field_map, type_map, default_type_raw)
            if obs is not None:
                observables.append(obs)

        logger.info(
            "APIFeed %s: normalized %d observables from %d items",
            self.url,
            len(observables),
            len(items),
        )
        return observables

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_auth(self, headers: dict) -> None:
        """Apply authentication to the request headers."""
        auth_type = self.auth_config.get("auth_type")
        if not auth_type:
            return

        if auth_type == "api_key":
            header_name = self.auth_config.get("api_key_header", "Authorization")
            api_key = self.auth_config.get("api_key_value", "")
            if api_key:
                headers[header_name] = api_key

        elif auth_type == "bearer":
            token = self.auth_config.get("token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

    def _map_item(
        self,
        item: dict,
        field_map: dict,
        type_map: dict,
        default_type_raw: str | None,
    ) -> RawObservable | None:
        """Map a single JSON item to a RawObservable using the field map."""
        # Extract value
        value_field = field_map.get("value", "value")
        value = _extract_field(item, value_field)
        if not value or not isinstance(value, (str, int, float)):
            return None
        value = str(value).strip()
        if not value:
            return None

        # For ip:port feeds like ThreatFox, strip the port
        obs_type = self._resolve_type(item, field_map, type_map, default_type_raw)
        if obs_type == ObservableType.IP_ADDR and ":" in value:
            value = value.split(":")[0]

        if obs_type is None:
            return None

        # Extract native confidence (optional)
        native_confidence: int | None = None
        if "native_confidence" in field_map:
            conf_field = field_map["native_confidence"]
            raw_conf = _extract_field(item, conf_field)
            if raw_conf is not None:
                try:
                    native_confidence = int(raw_conf)
                except (ValueError, TypeError):
                    pass

        return RawObservable(
            type=obs_type,
            value=value,
            native_confidence=native_confidence,
        )

    def _resolve_type(
        self,
        item: dict,
        field_map: dict,
        type_map: dict,
        default_type_raw: str | None,
    ) -> ObservableType | None:
        """Determine the ObservableType for a single item."""
        # Try to get type from the item via field_map
        if "type" in field_map:
            type_field = field_map["type"]
            raw_type = _extract_field(item, type_field)
            if raw_type and isinstance(raw_type, str):
                # Check type_map first
                if type_map and raw_type in type_map:
                    try:
                        return ObservableType(type_map[raw_type])
                    except ValueError:
                        logger.debug(
                            "type_map value %r is not a valid ObservableType",
                            type_map[raw_type],
                        )
                # Try direct enum match
                try:
                    return ObservableType(raw_type)
                except ValueError:
                    logger.debug("Raw type %r not in type_map or enum", raw_type)
                    # Fall through to default

        # Fall back to default_type
        if default_type_raw:
            try:
                return ObservableType(default_type_raw)
            except ValueError:
                logger.warning("Invalid default_type: %r", default_type_raw)

        return None
