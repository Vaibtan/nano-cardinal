"""ARQ worker settings — background task runner for Orion.

Start with:  python -m arq app.workers.worker.WorkerSettings
"""

from arq.connections import RedisSettings

from app.config import settings


async def startup(ctx: dict) -> None:
    """Initialise shared resources (DB pool, HTTP client, etc.)."""


async def shutdown(ctx: dict) -> None:
    """Clean up shared resources."""


class WorkerSettings:
    """ARQ worker configuration."""

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions: list = []
    on_startup = startup
    on_shutdown = shutdown
