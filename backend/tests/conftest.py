"""Shared test fixtures — PostgreSQL + httpx test client."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import get_db, session_has_pending_writes
from app.main import app

_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://orion:orion_secret@localhost:5433"
    "/orion_test",
)

# ── Safety guard: refuse to run against a non-test database ──────
_db_name = _TEST_DB_URL.rsplit("/", 1)[-1]
if "test" not in _db_name.lower():
    raise RuntimeError(
        f"Refusing to run tests: database '{_db_name}' does not "
        "contain 'test' in its name. Set TEST_DATABASE_URL to a "
        "dedicated test database.",
    )

_engine = create_async_engine(
    _TEST_DB_URL, echo=False, poolclass=NullPool,
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_cfg() -> Config:
    """Build an Alembic Config pointing at our migrations."""
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(_BACKEND_DIR / "alembic"),
    )
    return cfg


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _apply_migrations():
    """Run Alembic migrations once per test session.

    Uses ``DROP SCHEMA … CASCADE`` for a clean slate, then runs
    ``alembic upgrade head`` so the test schema always mirrors the
    real migration path (not just ORM metadata).
    """
    # Preflight: verify the database is reachable.
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.exit(
            f"Cannot connect to test database at {_TEST_DB_URL}.\n"
            "Ensure PostgreSQL is running and 'orion_test' DB exists:\n"
            "  docker compose up -d postgres\n"
            "  docker exec <pg-container> createdb -U orion orion_test"
            f"\nError: {exc}",
            returncode=1,
        )

    # Clean slate → run migrations.
    async with _engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector"),
        )

        def _run_alembic(sync_conn):
            cfg = _alembic_cfg()
            cfg.attributes["connection"] = sync_conn
            command.upgrade(cfg, "head")

        await conn.run_sync(_run_alembic)

    yield

    # Teardown: drop everything and release connections.
    async with _engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await _engine.dispose()


@pytest.fixture(autouse=True)
async def _db_session(_apply_migrations):
    """Provide a transactional scope around each test.

    Opens a connection, starts a transaction, then binds a session
    to it.  The app's ``get_db`` dependency is overridden to yield
    this session.  On teardown the outer transaction is rolled back,
    giving perfect isolation without needing TRUNCATE.
    """
    async with _engine.connect() as connection:
        trans = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False,
        )

        # When app code calls session.commit() it commits the
        # SAVEPOINT, not the outer transaction.  This listener
        # re-opens a fresh SAVEPOINT so subsequent operations still
        # work inside the outer transaction.
        await connection.begin_nested()

        @event.listens_for(
            session.sync_session, "after_transaction_end",
        )
        def _restart_savepoint(sess, transaction):
            if connection.closed or connection.invalidated:
                return
            if not connection.in_nested_transaction():
                connection.sync_connection.begin_nested()

        async def _override() -> AsyncGenerator[AsyncSession, None]:
            try:
                yield session
                if session_has_pending_writes(session):
                    await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                session.info.pop("_orion_has_write_statement", None)

        app.dependency_overrides[get_db] = _override
        yield session

        await session.close()
        await trans.rollback()

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as ac:
        yield ac
