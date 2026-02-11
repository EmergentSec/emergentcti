"""Feed connector factory and registry.

Provides a mapping from FeedType enum values to their connector implementations,
and a factory function to instantiate the correct connector for a given Feed model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cti.feeds.api_connector import APIFeedConnector
from cti.feeds.base import BaseFeedConnector, FeedResult
from cti.feeds.file_connector import FileFeedConnector
from cti.feeds.scraper_connector import ScraperFeedConnector
from cti.feeds.taxii_connector import TAXIIFeedConnector
from cti.models.feed import FeedType

if TYPE_CHECKING:
    from cti.models.feed import Feed

# Maps each FeedType to its connector class.
CONNECTOR_MAP: dict[FeedType, type[BaseFeedConnector]] = {
    FeedType.api: APIFeedConnector,
    FeedType.taxii: TAXIIFeedConnector,
    FeedType.file: FileFeedConnector,
    FeedType.scraper: ScraperFeedConnector,
}


def get_connector(feed: Feed) -> BaseFeedConnector:
    """Instantiate the appropriate feed connector for a given Feed model.

    Args:
        feed: The Feed ORM model instance. Its ``feed_type`` attribute
              determines which connector class is used.

    Returns:
        An initialized (but not yet connected) feed connector instance.

    Raises:
        ValueError: If the feed's type has no registered connector.
    """
    connector_class = CONNECTOR_MAP.get(feed.feed_type)
    if connector_class is None:
        raise ValueError(
            f"No connector registered for feed type: {feed.feed_type.value}"
        )
    return connector_class(feed)


__all__ = [
    "CONNECTOR_MAP",
    "APIFeedConnector",
    "BaseFeedConnector",
    "FeedResult",
    "FileFeedConnector",
    "ScraperFeedConnector",
    "TAXIIFeedConnector",
    "get_connector",
]
