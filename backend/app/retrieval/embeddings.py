"""
File purpose:
- Builds FastEmbed embeddings for document chunks and search queries.
- Uses one consistent embedding model for both indexing and retrieval.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config.settings import EMBEDDING_MODEL, VECTOR_DIMENSION


@lru_cache(maxsize=1)
# Gets embedding model.
def _get_embedding_model() -> Any:
    # Prefer LangChain wrapper so embedding flow can plug into LC modules
    # while retaining FastEmbed as the concrete embedding backend.
    try:
        from langchain_community.embeddings import FastEmbedEmbeddings

        return FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)
    except Exception:
        pass

    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "fastembed is not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    return TextEmbedding(model_name=EMBEDDING_MODEL)
# Validates vector dimension before the next step.
def _validate_vector_dimension(vector: list[float]) -> None:
    if len(vector) != VECTOR_DIMENSION:
        raise RuntimeError(
            f"Embedding dimension mismatch: expected {VECTOR_DIMENSION}, got {len(vector)}. "
            "Check EMBEDDING_MODEL and VECTOR_DIMENSION in backend/.env."
        )
# Embeds texts.
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    sanitized_texts = [text.strip() for text in texts if text and text.strip()]
    if not sanitized_texts:
        return []

    # Uses FastEmbed via LangChain when available; otherwise direct fastembed.
    model = _get_embedding_model()
    if hasattr(model, "embed_documents"):
        output = model.embed_documents(sanitized_texts)
    else:
        output = [vector.tolist() for vector in model.embed(sanitized_texts)]
    for vector in output:
        _validate_vector_dimension(vector)
    return output
# Embeds query.
def embed_query(text: str) -> list[float]:
    query = text.strip()
    if not query:
        raise ValueError("query must not be empty.")

    [vector] = embed_texts([query])
    return vector


