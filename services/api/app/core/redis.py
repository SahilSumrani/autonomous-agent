from typing import Optional
import redis.asyncio as aioredis
from packages.config.settings import settings
from services.api.app.core.logging import get_logger

logger = get_logger("redis")

_redis_pool: Optional[aioredis.ConnectionPool] = None


def get_redis_pool() -> aioredis.ConnectionPool:
    """Initialize or return the global Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
    return _redis_pool


def get_redis() -> aioredis.Redis:
    """Return an async Redis client instance from the pool."""
    pool = get_redis_pool()
    return aioredis.Redis(connection_pool=pool)


async def check_redis_health() -> bool:
    """Ping Redis to verify connectivity."""
    try:
        client = get_redis()
        pong = await client.ping()
        return bool(pong)
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        return False


async def close_redis() -> None:
    """Close Redis pool connections gracefully on shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis connection pool disconnected")
