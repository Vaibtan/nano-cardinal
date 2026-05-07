"""Redis client for ARQ job queue, cache, and SSE Pub/Sub."""

from redis.asyncio import Redis

from app.config import settings

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_redis() -> Redis:
    """Return the shared Redis client."""
    return redis_client
