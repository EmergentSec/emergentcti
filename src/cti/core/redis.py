from redis.asyncio import Redis

from cti.core.config import get_settings


def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)
