"""Embedding utilities and vector dimension constants."""

from __future__ import annotations

import hashlib

import httpx

from app.config import settings

# The DB column dimension is fixed at schema creation time.
# Changing this requires a new Alembic migration to ALTER the column.
VECTOR_DIMENSION: int = 768

EMBEDDING_DIMS: dict[str, int] = {
    "text-embedding-004": 768,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "nomic-embed-text": 768,
}


class EmbeddingDimensionMismatchError(RuntimeError):
    """Configured embedding model dimension does not match the DB column."""


class EmbeddingProviderError(RuntimeError):
    """Embedding provider call failed or returned invalid data."""


def get_embedding_size() -> int | None:
    """Return the dimension of the configured embedding model.

    Returns ``None`` if ``EMBEDDING_MODEL`` is unknown — callers
    should treat that as an error, not a default.
    """
    return EMBEDDING_DIMS.get(settings.EMBEDDING_MODEL)


def validate_embedding_dimension() -> None:
    """Fail fast if the configured embedding model would write
    vectors of a different dimension than the DB column expects.

    Called at FastAPI and ARQ worker startup so the process refuses
    to come up in a misconfigured state instead of failing on the
    first INSERT.
    """
    expected = get_embedding_size()
    if expected is None:
        raise EmbeddingDimensionMismatchError(
            f"Unknown EMBEDDING_MODEL '{settings.EMBEDDING_MODEL}'. "
            f"Add it to EMBEDDING_DIMS in app/embeddings.py with its "
            f"vector dimension. Known models: "
            f"{sorted(EMBEDDING_DIMS)}.",
        )
    if expected != VECTOR_DIMENSION:
        raise EmbeddingDimensionMismatchError(
            f"EMBEDDING_MODEL '{settings.EMBEDDING_MODEL}' produces "
            f"{expected}-dim vectors, but the leads.embedding column "
            f"is VECTOR({VECTOR_DIMENSION}). Either pick a model "
            f"matching {VECTOR_DIMENSION} dims, or run a migration "
            f"that ALTERs the column to {expected}.",
        )


def generate_mock_embedding(text: str) -> list[float]:
    """Generate a deterministic unit-length vector from text via SHA-256.

    Used in mock/test mode to avoid calling a real embedding API.
    """
    h = hashlib.sha256(text.encode()).digest()
    raw = list(h) * (VECTOR_DIMENSION // len(h) + 1)
    vector = [float(b) / 255.0 for b in raw[:VECTOR_DIMENSION]]
    norm = sum(v * v for v in vector) ** 0.5
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding from the configured provider."""
    if settings.USE_MOCK_ENRICHMENT:
        return generate_mock_embedding(text)
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai":
        vector = await _openai_embedding(text)
    elif provider == "gemini":
        vector = await _gemini_embedding(text)
    elif provider == "ollama":
        vector = await _ollama_embedding(text)
    else:
        raise EmbeddingProviderError(
            f"Unknown EMBEDDING_PROVIDER '{settings.EMBEDDING_PROVIDER}'",
        )
    if len(vector) != VECTOR_DIMENSION:
        raise EmbeddingDimensionMismatchError(
            f"Provider returned {len(vector)} dimensions, expected "
            f"{VECTOR_DIMENSION}",
        )
    return _normalize(vector)


async def _openai_embedding(text: str) -> list[float]:
    if not settings.OPENAI_API_KEY:
        raise EmbeddingProviderError("OPENAI_API_KEY is required")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={"model": settings.EMBEDDING_MODEL, "input": text},
        )
    response.raise_for_status()
    data = response.json()
    return [float(value) for value in data["data"][0]["embedding"]]


async def _gemini_embedding(text: str) -> list[float]:
    if not settings.GEMINI_API_KEY:
        raise EmbeddingProviderError("GEMINI_API_KEY is required")
    model = settings.EMBEDDING_MODEL
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:embedContent?key={settings.GEMINI_API_KEY}"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            json={"content": {"parts": [{"text": text}]}},
        )
    response.raise_for_status()
    data = response.json()
    return [float(value) for value in data["embedding"]["values"]]


async def _ollama_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings",
            json={"model": settings.EMBEDDING_MODEL, "prompt": text},
        )
    response.raise_for_status()
    data = response.json()
    return [float(value) for value in data["embedding"]]


def _normalize(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]
