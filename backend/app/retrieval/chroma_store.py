"""
File purpose:
- Manages the Chroma client and collection lifecycle for chunk vectors.
- Provides upsert, delete, search, and health helpers for Phase 4.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config.settings import VECTOR_COLLECTION, VECTOR_SEARCH_LIMIT, VECTOR_STORE_PATH


# Detailed function explanation:
# - Purpose: `_get_chroma_symbols` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _get_chroma_symbols():
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "chromadb is not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc
    return chromadb


@lru_cache(maxsize=1)
# Detailed function explanation:
# - Purpose: `get_chroma_client` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def get_chroma_client():
    chromadb = _get_chroma_symbols()
    return chromadb.PersistentClient(path=VECTOR_STORE_PATH)


# Detailed function explanation:
# - Purpose: `get_collection` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=VECTOR_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


# Detailed function explanation:
# - Purpose: `ensure_collection` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def ensure_collection() -> None:
    get_collection()


# Detailed function explanation:
# - Purpose: `vector_store_health` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def vector_store_health() -> dict[str, str]:
    try:
        collection = get_collection()
        collection.count()
    except Exception as exc:
        return {"status": "disconnected", "collection": VECTOR_COLLECTION, "detail": str(exc)}
    return {"status": "connected", "collection": VECTOR_COLLECTION}


# Detailed function explanation:
# - Purpose: `delete_document_vectors` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def delete_document_vectors(document_id: int) -> None:
    get_collection().delete(where={"document_id": int(document_id)})


# Detailed function explanation:
# - Purpose: `upsert_chunk_vectors` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def upsert_chunk_vectors(records: list[dict[str, Any]]) -> None:
    if not records:
        return

    collection = get_collection()
    ids: list[str] = []
    documents: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict[str, Any]] = []

    for record in records:
        metadata = record["metadata"]
        ids.append(str(record["id"]))
        documents.append(str(record["document"]))
        embeddings.append(record["embedding"])
        metadatas.append(
            {
                "document_id": int(metadata["document_id"]),
                "chunk_index": int(metadata["chunk_index"]),
                "page_number": int(metadata["page_number"]),
                "owner_user_id": int(metadata["owner_user_id"]),
                "source_name": str(metadata["source_name"]),
                "permissions_tags": str(metadata["permissions_tags"]),
            }
        )

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


# Detailed function explanation:
# - Purpose: `search_vectors` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def search_vectors(
    query_vector: list[float],
    *,
    limit: int | None = None,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    owner_user_id: int | None = None,
) -> list[dict[str, Any]]:
    collection = get_collection()

    filters: list[dict[str, Any]] = []
    if document_id is not None:
        filters.append({"document_id": int(document_id)})
    elif document_ids is not None:
        if not document_ids:
            return []
        filters.append({"document_id": {"$in": [int(item) for item in document_ids]}})
    if owner_user_id is not None:
        filters.append({"owner_user_id": int(owner_user_id)})

    where: dict[str, Any] | None = None
    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=limit or VECTOR_SEARCH_LIMIT,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    ids = results.get("ids", [[]])
    documents = results.get("documents", [[]])
    metadatas = results.get("metadatas", [[]])
    distances = results.get("distances", [[]])

    normalized_hits: list[dict[str, Any]] = []
    for hit_id, document, metadata, distance in zip(
        ids[0] if ids else [],
        documents[0] if documents else [],
        metadatas[0] if metadatas else [],
        distances[0] if distances else [],
        strict=True,
    ):
        metadata = metadata or {}
        normalized_hits.append(
            {
                "id": str(hit_id),
                "score": float(distance),
                "document_id": int(metadata.get("document_id", 0)),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "page_number": int(metadata.get("page_number", -1)),
                "owner_user_id": int(metadata.get("owner_user_id", -1)),
                "source_name": str(metadata.get("source_name", "")),
                "permissions_tags": str(metadata.get("permissions_tags", "[]")),
                "content": str(document or ""),
            }
        )
    return normalized_hits
