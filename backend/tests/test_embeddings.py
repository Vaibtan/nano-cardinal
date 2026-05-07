"""Tests for embedding dimension validation."""

import pytest

from app.embeddings import (
    VECTOR_DIMENSION,
    EmbeddingDimensionMismatchError,
    validate_embedding_dimension,
)


def test_validate_passes_for_matching_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.embeddings.settings.EMBEDDING_MODEL",
        "text-embedding-004",
    )
    validate_embedding_dimension()


def test_validate_rejects_unknown_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.embeddings.settings.EMBEDDING_MODEL",
        "totally-made-up-model",
    )
    with pytest.raises(EmbeddingDimensionMismatchError) as exc:
        validate_embedding_dimension()
    assert "Unknown EMBEDDING_MODEL" in str(exc.value)


def test_validate_rejects_dimension_mismatch(monkeypatch) -> None:
    """A known model whose dim differs from the column must error."""
    assert VECTOR_DIMENSION == 768  # column dimension assumption
    monkeypatch.setattr(
        "app.embeddings.settings.EMBEDDING_MODEL",
        "text-embedding-3-small",  # 1536 dims
    )
    with pytest.raises(EmbeddingDimensionMismatchError) as exc:
        validate_embedding_dimension()
    msg = str(exc.value)
    assert "1536" in msg
    assert "768" in msg
