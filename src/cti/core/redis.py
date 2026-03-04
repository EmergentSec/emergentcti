"""Redis async client and cache helpers."""

from __future__ import annotations

import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ── Module-level singleton ───────────────────────────────────────────────

_redis_client: Redis | None = None


# ── Lifecycle ────────────────────────────────────────────────────────────

async def init_redis(url: str) -> Redis:
    """Create and store the global Redis client. Called during app lifespan startup."""
    global _redis_client  # noqa: PLW0603
    _redis_client = Redis.from_url(url, decode_responses=True)
    # Verify connectivity
    await _redis_client.ping()
    logger.info("Redis connection established")
    return _redis_client


async def close_redis() -> None:
    """Gracefully close the Redis connection. Called during app lifespan shutdown."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


# ── Accessor ─────────────────────────────────────────────────────────────

def get_redis() -> Redis:
    """Return the active Redis client. Raises if init_redis() has not been called."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialised — call init_redis() first")
    return _redis_client


# ── Cache helpers ────────────────────────────────────────────────────────

async def cache_get(key: str) -> str | None:
    """Retrieve a cached value by key, or None if missing/expired."""
    client = get_redis()
    return await client.get(key)


async def cache_set(key: str, value: str, ttl_seconds: int = 300) -> None:
    """Store a value in cache with a TTL (default 5 minutes)."""
    client = get_redis()
    await client.set(key, value, ex=ttl_seconds)


async def invalidate_blocklist_cache() -> None:
    """Delete all cached blocklist entries (keys matching ``blocklist:*``).

    Uses async SCAN to avoid blocking Redis on large key spaces.
    """
    client = get_redis()
    deleted = 0
    async for key in client.scan_iter(match="blocklist:*", count=200):
        await client.delete(key)
        deleted += 1
    if deleted:
        logger.info("Invalidated %d blocklist cache entries", deleted)
