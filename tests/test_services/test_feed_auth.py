"""Unit tests for feed auth_config validation."""

from __future__ import annotations

import pytest

from cti.services.feed_auth import (
    AuthConfigValidationError,
    extract_partial_secret,
    validate_auth_config,
)


def test_validate_bearer_accepts_api_key_value_mirror() -> None:
    cfg = validate_auth_config(
        {"auth_type": "bearer", "api_key_value": "secret-token"},
        feed_url=None,
    )
    assert cfg["token"] == "secret-token"
    assert cfg["api_key_value"] == "secret-token"


def test_validate_url_template_requires_placeholder_in_url() -> None:
    with pytest.raises(AuthConfigValidationError, match="\\{api_key\\}"):
        validate_auth_config(
            {"auth_type": "url_template", "api_key_value": "k"},
            feed_url="https://example.com/no-placeholder",
        )


def test_extract_partial_secret_rejects_non_string() -> None:
    with pytest.raises(AuthConfigValidationError, match="must be a string"):
        extract_partial_secret({"api_key_value": 12345})
