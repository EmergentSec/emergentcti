"""Test fixtures scoped to the API test suite."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_scheduler() -> Generator[None, None, None]:
    """Patch sync_feed_jobs so API tests don't need a running scheduler."""
    with patch("cti.services.scheduler.sync_feed_jobs", new_callable=AsyncMock):
        yield
