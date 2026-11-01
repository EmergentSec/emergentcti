"""Validate feed auth_config shapes for create, update, and repair detection."""

from __future__ import annotations

REPAIR_MESSAGE = (
    "Stored auth configuration is invalid; provide a full auth_config including auth_type."
)


class AuthConfigValidationError(ValueError):
    """Raised when auth_config fails structural validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _require_non_empty_str(value: object, field_label: str) -> str:
    if not isinstance(value, str):
        raise AuthConfigValidationError(
            f"auth_config {field_label} must be a non-empty string"
        )
    stripped = value.strip()
    if not stripped:
        raise AuthConfigValidationError(
            f"auth_config {field_label} must be a non-empty string"
        )
    return stripped


def validate_auth_config(auth_config: dict, *, feed_url: str | None) -> dict:
    """Validate and normalize a full auth_config dict."""
    if not isinstance(auth_config, dict):
        raise AuthConfigValidationError("auth_config must be an object")

    auth_type_raw = auth_config.get("auth_type")
    if not isinstance(auth_type_raw, str) or not auth_type_raw.strip():
        raise AuthConfigValidationError("auth_config auth_type is required")

    auth_type = auth_type_raw.strip()

    if auth_type == "api_key":
        header = _require_non_empty_str(
            auth_config.get("api_key_header"), "api_key_header"
        )
        value = _require_non_empty_str(
            auth_config.get("api_key_value"), "api_key_value"
        )
        return {
            "auth_type": "api_key",
            "api_key_header": header,
            "api_key_value": value,
        }

    if auth_type == "bearer":
        token_raw = auth_config.get("token")
        api_key_raw = auth_config.get("api_key_value")
        secret: str | None = None
        if isinstance(token_raw, str) and token_raw.strip():
            secret = token_raw.strip()
        elif isinstance(api_key_raw, str) and api_key_raw.strip():
            secret = api_key_raw.strip()
        if secret is None:
            raise AuthConfigValidationError(
                "auth_config token must be a non-empty string"
            )
        return {
            "auth_type": "bearer",
            "token": secret,
            "api_key_value": secret,
        }

    if auth_type == "url_template":
        value = _require_non_empty_str(
            auth_config.get("api_key_value"), "api_key_value"
        )
        if not feed_url or "{api_key}" not in feed_url:
            raise AuthConfigValidationError(
                "auth_config url_template requires the feed URL to contain '{api_key}'"
            )
        return {"auth_type": "url_template", "api_key_value": value}

    raise AuthConfigValidationError(
        f"auth_config auth_type {auth_type!r} is not supported"
    )


def stored_auth_needs_repair(auth_config: dict, *, feed_url: str | None) -> bool:
    """True when encrypted auth exists but fails :func:`validate_auth_config`."""
    try:
        validate_auth_config(auth_config, feed_url=feed_url)
    except AuthConfigValidationError:
        return True
    return False


def extract_partial_secret(partial: dict) -> str | None:
    """Return a non-empty secret from a partial rotation payload, or None for no-op."""
    for key in ("api_key_value", "token"):
        raw = partial.get(key)
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped:
                return stripped
    return None
