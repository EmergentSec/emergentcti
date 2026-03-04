from cti.feeds.api_connector import APIFeedConnector
from cti.feeds.base import BaseFeedConnector
from cti.feeds.file_connector import FileFeedConnector
from cti.feeds.scraper_connector import ScraperFeedConnector
from cti.models.feed import Feed, FeedType


def get_connector(feed: Feed, auth_config: dict | None = None) -> BaseFeedConnector:
    """Factory to create the right connector for a feed."""
    connectors = {
        FeedType.API: APIFeedConnector,
        FeedType.FILE: FileFeedConnector,
        FeedType.SCRAPER: ScraperFeedConnector,
    }
    connector_cls = connectors.get(feed.feed_type)
    if not connector_cls:
        raise ValueError(f"Unknown feed type: {feed.feed_type}")
    return connector_cls(url=feed.url or "", config=feed.config, auth_config=auth_config)
