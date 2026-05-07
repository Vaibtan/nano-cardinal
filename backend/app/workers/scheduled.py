"""Scheduled ARQ tasks for signals and sequences."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.services.sequences import execute_due_enrollments
from app.services.signals import run_mock_signal_scan

logger = logging.getLogger(__name__)

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


async def scan_signals(ctx: dict) -> None:
    """ARQ task: run mock funding/hiring/LinkedIn/news monitors."""
    async with _worker_session_factory() as db:
        created = await run_mock_signal_scan(db)
        await db.commit()
        logger.info("Signal scan created %s signals", created)


async def execute_sequences(ctx: dict) -> None:
    """ARQ task: execute due sequence enrollments."""
    async with _worker_session_factory() as db:
        executed = await execute_due_enrollments(db)
        await db.commit()
        logger.info("Sequence executor handled %s enrollments", executed)
