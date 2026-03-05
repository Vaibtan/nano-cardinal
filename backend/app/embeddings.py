"""Embedding utilities and vector dimension constants."""

from app.config import settings

# The DB column dimension is fixed at schema creation time.
# Changing this requires a new Alembic migration to ALTER the column.
VECTOR_DIMENSION: int = 768

_EMBEDDING_DIMS: dict[str, int] = {
    "text-embedding-004": 768,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "nomic-embed-text": 768,
}


def get_embedding_size() -> int:
    """Return the dimension of the configured embedding model.

    This is used when *generating* embeddings — not for the DB
    column definition, which always uses ``VECTOR_DIMENSION``.
    Callers should verify at startup that ``get_embedding_size()``
    matches ``VECTOR_DIMENSION``.
    """
    return _EMBEDDING_DIMS.get(settings.EMBEDDING_MODEL, 768)
