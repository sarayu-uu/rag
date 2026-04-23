"""
File purpose:
- Coordinates embedding generation and vector-store indexing for stored chunks.
- Exposes high-level helpers used by ingestion and retrieval routes.
"""

from __future__ import annotations

import json
from typing import Any

from app.models.mysql import DocumentChunk
from app.retrieval.embeddings import embed_query, embed_texts
from app.retrieval.chroma_store import (
    delete_document_vectors,
    ensure_collection,
    search_vectors,
    upsert_chunk_vectors,
    vector_store_health,
)


def _chunk_to_vector_record(chunk: DocumentChunk, vector: list[float]) -> dict[str, Any]:
    return {
        "id": str(chunk.id),
        "document": chunk.content,
        "metadata": {
            "document_id": int(chunk.document_id),
            "chunk_index": int(chunk.chunk_index),
            "page_number": int(chunk.page_number if chunk.page_number is not None else -1),
            "owner_user_id": int(chunk.owner_user_id if chunk.owner_user_id is not None else -1),
            "source_name": chunk.source_name,
            "permissions_tags": chunk.permissions_tags or "[]",
        },
        "embedding": vector,
    }


def ensure_vector_store_ready() -> None:
    ensure_collection()


def sync_document_chunks_to_vector_store(chunks: list[DocumentChunk]) -> dict[str, Any]:
    if not chunks:
        raise ValueError("At least one chunk is required for indexing.")

    document_id = int(chunks[0].document_id)
    vectors = embed_texts([chunk.content for chunk in chunks])
    records = [_chunk_to_vector_record(chunk, vector) for chunk, vector in zip(chunks, vectors, strict=True)]

    delete_document_vectors(document_id)
    upsert_chunk_vectors(records)

    return {
        "document_id": document_id,
        "indexed_chunk_count": len(records),
        "collection": vector_store_health().get("collection", ""),
    }


def clear_document_vectors(document_id: int) -> None:
    delete_document_vectors(document_id)


def search_chunk_text(
    query: str,
    *,
    limit: int,
    document_id: int | None = None,
) -> list[dict[str, Any]]:
    query_vector = embed_query(query)
    results = search_vectors(query_vector, limit=limit, document_id=document_id)

    normalized_results: list[dict[str, Any]] = []
    for result in results:
        permissions_tags: list[str] = []
        try:
            parsed = json.loads(result["permissions_tags"])
            if isinstance(parsed, list):
                permissions_tags = [tag for tag in parsed if isinstance(tag, str)]
        except json.JSONDecodeError:
            permissions_tags = []

        normalized_results.append(
            {
                "id": result["id"],
                "score": result["score"],
                "document_id": result["document_id"],
                "chunk_index": result["chunk_index"],
                "page_number": None if result["page_number"] < 0 else result["page_number"],
                "owner_user_id": None if result["owner_user_id"] < 0 else result["owner_user_id"],
                "source_name": result["source_name"],
                "permissions_tags": permissions_tags,
                "content": result["content"],
            }
        )

    return normalized_results
