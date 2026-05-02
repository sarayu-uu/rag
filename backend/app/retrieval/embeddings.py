"""
File purpose:
- Builds FastEmbed embeddings for document chunks and search queries.
- Uses one consistent embedding model for both indexing and retrieval.
"""

from __future__ import annotations

from functools import lru_cache

from app.config.settings import EMBEDDING_MODEL, VECTOR_DIMENSION


@lru_cache(maxsize=1)
# Detailed function explanation:
# - Purpose: `_get_embedding_model` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _get_embedding_model():
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "fastembed is not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    return TextEmbedding(model_name=EMBEDDING_MODEL)


# Detailed function explanation:
# - Purpose: `_validate_vector_dimension` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _validate_vector_dimension(vector: list[float]) -> None:
    if len(vector) != VECTOR_DIMENSION:
        raise RuntimeError(
            f"Embedding dimension mismatch: expected {VECTOR_DIMENSION}, got {len(vector)}. "
            "Check EMBEDDING_MODEL and VECTOR_DIMENSION in backend/.env."
        )


# Detailed function explanation:
# - Purpose: `embed_texts` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    sanitized_texts = [text.strip() for text in texts if text and text.strip()]
    if not sanitized_texts:
        return []

    model = _get_embedding_model()
    output = [vector.tolist() for vector in model.embed(sanitized_texts)]
    for vector in output:
        _validate_vector_dimension(vector)
    return output


# Detailed function explanation:
# - Purpose: `embed_query` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def embed_query(text: str) -> list[float]:
    query = text.strip()
    if not query:
        raise ValueError("query must not be empty.")

    [vector] = embed_texts([query])
    return vector
