"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


_WRITE_FLAG = "_orion_has_write_statement"


@event.listens_for(AsyncSession.sync_session_class, "do_orm_execute")
def _track_write_statements(orm_execute_state) -> None:
    """Mark session when a non-SELECT statement is executed.

    This covers Core/SQL expression writes executed via ``session.execute()``,
    which do not populate ``session.new/dirty/deleted``.
    """
    if (
        orm_execute_state.is_select
        or orm_execute_state.is_column_load
        or orm_execute_state.is_relationship_load
    ):
        return
    orm_execute_state.session.info[_WRITE_FLAG] = True


def session_has_pending_writes(session: AsyncSession) -> bool:
    """Return True if session contains ORM or Core-level writes."""
    if session.new or session.dirty or session.deleted:
        return True
    return bool(session.info.get(_WRITE_FLAG))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Only commits when the session has pending ORM-level changes,
    avoiding an unnecessary COMMIT round-trip on read-only routes.
    """
    async with async_session_factory() as session:
        try:
            yield session
            if session_has_pending_writes(session):
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            session.info.pop(_WRITE_FLAG, None)
