from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from datetime import datetime

from cti.models.observable import ObservableType

logger = logging.getLogger(__name__)


@dataclass
class RawObservable:
    """A single observable extracted from a feed before DB insertion."""

    type: ObservableType
    value: str
    native_confidence: int | None = None  # None = feed has no native scoring
    first_seen: datetime | None = None
    last_seen: datetime | None = None


@dataclass
class FeedResult:
    """Result of a feed ingestion run."""

    observables: list[RawObservable] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseFeedConnector(abc.ABC):
    """Abstract base class for all feed connectors."""

    def __init__(
        self,
        url: str,
        config: dict | None = None,
        auth_config: dict | None = None,
    ):
        self.url = url
        self.config = config or {}
        self.auth_config = auth_config or {}

    @abc.abstractmethod
    async def fetch(self) -> str | bytes | dict | list:
        """Fetch raw data from the feed source."""

    @abc.abstractmethod
    def normalize(self, raw_data: str | bytes | dict | list) -> list[RawObservable]:
        """Transform raw data into normalized observables."""

    async def ingest(self) -> FeedResult:
        """Template method: fetch -> normalize -> return result."""
        result = FeedResult()
        try:
            raw_data = await self.fetch()
            result.observables = self.normalize(raw_data)
        except Exception as e:
            logger.error(
                "Feed ingestion failed for %s: %s", self.url, e, exc_info=True
            )
            result.errors.append(str(e))
        return result
