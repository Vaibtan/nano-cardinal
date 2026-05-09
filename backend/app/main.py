"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    analytics,
    events,
    health,
    icps,
    inbound,
    leads,
    personalization,
    sender,
    sequences,
    signals,
    tam,
)
from app.embeddings import validate_embedding_dimension


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    validate_embedding_dimension()
    yield


app = FastAPI(
    title="Orion",
    description="AI precision outbound engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1")
app.include_router(icps.router, prefix="/api/v1")
app.include_router(sender.router, prefix="/api/v1")
app.include_router(leads.router, prefix="/api/v1")
app.include_router(tam.router, prefix="/api/v1")
app.include_router(inbound.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(personalization.router, prefix="/api/v1")
app.include_router(personalization.personalize_router, prefix="/api/v1")
app.include_router(sequences.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
