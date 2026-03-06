"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health, icps, leads, sender, tam

app = FastAPI(
    title="Orion",
    description="AI precision outbound engine",
    version="0.1.0",
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
