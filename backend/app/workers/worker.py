"""ARQ worker settings — background task runner for Orion.

Start with:  python -m arq app.workers.worker.WorkerSettings
"""

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import settings
from app.embeddings import validate_embedding_dimension
from app.workers.enrichment_worker import enrich_lead
from app.workers.personalization_worker import stream_draft_tokens
from app.workers.scheduled import execute_sequences, scan_signals


async def startup(ctx: dict) -> None:
    """Initialise shared resources (DB pool, HTTP client, etc.)."""
    validate_embedding_dimension()


async def shutdown(ctx: dict) -> None:
    """Clean up shared resources."""


class WorkerSettings:
    """ARQ worker configuration."""

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [
        enrich_lead,
        scan_signals,
        execute_sequences,
        stream_draft_tokens,
    ]
    cron_jobs = [
        cron(scan_signals, minute={0, 15, 30, 45}, run_at_startup=True),
        cron(execute_sequences, minute={0, 15, 30, 45}),
    ]
    on_startup = startup
    on_shutdown = shutdown
