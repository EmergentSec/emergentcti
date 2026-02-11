"""Base feed connector abstract class.

All feed connectors inherit from BaseFeedConnector and implement
the connect(), fetch(), and normalize() methods. The ingest() method
is a template method that orchestrates the full ingestion pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from cti.models.feed import Feed
from cti.schemas.observable import ObservableCreate
from cti.services.feed_service import get_feed_auth_config

logger = logging.getLogger(__name__)


@dataclass
class FeedResult:
    """Result of a single feed ingestion run."""

    observables: list[ObservableCreate] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    raw_record_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def observable_count(self) -> int:
        return len(self.observables)

    def finalize(self) -> None:
        """Mark the run as completed and compute duration."""
        self.completed_at = datetime.now(UTC)
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()


class BaseFeedConnector(ABC):
    """Abstract base class for all feed connectors.

    Subclasses must implement:
        - connect(): Validate connectivity / credentials.
        - fetch(): Retrieve raw data from the source.
        - normalize(raw_data): Transform raw data into ObservableCreate instances.

    The ingest() template method orchestrates the full pipeline:
        connect -> fetch -> normalize -> return FeedResult
    """

    def __init__(self, feed: Feed) -> None:
        self.feed = feed
        self.feed_id = feed.id
        self.feed_name = feed.name
        self.url = feed.url
        self.config: dict[str, Any] = feed.config or {}
        self.auth_config: dict[str, Any] = get_feed_auth_config(feed) or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}[{feed.name}]")

    @abstractmethod
    async def connect(self) -> None:
        """Validate connectivity and credentials for the feed source.

        Raises:
            ConnectionError: If the source is unreachable or credentials are invalid.
        """

    @abstractmethod
    async def fetch(self) -> Any:
        """Retrieve raw data from the feed source.

        Returns:
            Raw data in whatever format the source provides (JSON, text, bytes, etc.).
        """

    @abstractmethod
    async def normalize(self, raw_data: Any) -> list[ObservableCreate]:
        """Transform raw data into a list of ObservableCreate instances.

        Args:
            raw_data: The raw data returned by fetch().

        Returns:
            List of validated ObservableCreate schemas ready for database insertion.
        """

    async def ingest(self) -> FeedResult:
        """Template method that executes the full ingestion pipeline.

        Orchestrates: connect -> fetch -> normalize, collecting errors
        and metadata along the way.

        Returns:
            A FeedResult with the observables, metadata, and any errors.
        """
        result = FeedResult()

        try:
            self.logger.info("Connecting to feed source")
            await self.connect()
        except Exception as exc:
            msg = f"Connection failed: {exc}"
            self.logger.error(msg)
            result.errors.append(msg)
            result.finalize()
            return result

        try:
            self.logger.info("Fetching data from feed source")
            raw_data = await self.fetch()
        except Exception as exc:
            msg = f"Fetch failed: {exc}"
            self.logger.error(msg)
            result.errors.append(msg)
            result.finalize()
            return result

        try:
            self.logger.info("Normalizing raw data into observables")
            observables = await self.normalize(raw_data)
            result.observables = observables
            self.logger.info(
                "Ingestion complete: %d observables produced", len(observables)
            )
        except Exception as exc:
            msg = f"Normalization failed: {exc}"
            self.logger.error(msg)
            result.errors.append(msg)

        result.finalize()
        return result
