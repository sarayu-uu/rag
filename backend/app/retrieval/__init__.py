"""
Retrieval package for Phase 4 vector indexing and similarity search.
"""

from app.retrieval.service import (
    clear_document_vectors,
    ensure_vector_store_ready,
    search_chunk_text,
    sync_document_chunks_to_vector_store,
)

__all__ = [
    "clear_document_vectors",
    "ensure_vector_store_ready",
    "search_chunk_text",
    "sync_document_chunks_to_vector_store",
]
