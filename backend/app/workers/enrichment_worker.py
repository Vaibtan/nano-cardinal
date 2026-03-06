"""ARQ task functions for lead enrichment."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.services.enrichment import (
    RealIntegrationNotImplementedError,
    run_enrichment_pipeline,
)

logger = logging.getLogger(__name__)

# Workers create their own engine to avoid sharing with the API process.
_worker_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)
_worker_session_factory = async_sessionmaker(
    _worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def _commit_failed_state(db: AsyncSession, lead_id: str) -> None:
    """Persist FAILED status before returning or retrying."""
    try:
        await db.commit()
    except Exception:
        logger.warning(
            "Could not commit FAILED status for lead %s", lead_id,
            exc_info=True,
        )
        await db.rollback()
        raise


async def enrich_lead(ctx: dict, lead_id: str) -> None:
    """ARQ task: run the full enrichment pipeline for a lead.

    On enrichment failure the pipeline sets FAILED status and flushes
    it, then re-raises.  We commit that FAILED state before
    propagating the exception so ARQ can retry the task while the
    lead's status accurately reflects the last attempt.
    """
    logger.info("Starting enrichment for lead %s", lead_id)
    async with _worker_session_factory() as db:
        try:
            await run_enrichment_pipeline(lead_id, db)
            await db.commit()
            logger.info("Enrichment complete for lead %s", lead_id)
        except RealIntegrationNotImplementedError:
            await _commit_failed_state(db, lead_id)
            logger.error(
                "Real enrichment requested for lead %s but integrations "
                "are not implemented yet",
                lead_id,
            )
        except Exception:
            await _commit_failed_state(db, lead_id)
            raise
