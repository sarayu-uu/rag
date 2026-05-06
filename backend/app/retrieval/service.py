"""
File purpose:
- Coordinates embedding generation and vector-store indexing for stored chunks.
- Exposes high-level helpers used by ingestion and retrieval routes.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.models.mysql import DocumentChunk, SessionLocal
from app.retrieval.embeddings import embed_query, embed_texts
from app.retrieval.chroma_store import (
    delete_document_vectors,
    ensure_collection,
    get_chroma_client,
    search_vectors,
    upsert_chunk_vectors,
    vector_store_health,
)
# Chunks to vector record.
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
# Ensures vector store ready is ready.
def ensure_vector_store_ready() -> None:
    ensure_collection()
# Syncs document chunks to vector store.
def sync_document_chunks_to_vector_store(chunks: list[DocumentChunk]) -> dict[str, Any]:
    if not chunks:
        raise ValueError("At least one chunk is required for indexing.")

    document_id = int(chunks[0].document_id)
    #embeding happens here
    vectors = embed_texts([chunk.content for chunk in chunks])
    records = [_chunk_to_vector_record(chunk, vector) for chunk, vector in zip(chunks, vectors, strict=True)]

    delete_document_vectors(document_id)
    upsert_chunk_vectors(records)

    return {
        "document_id": document_id,
        "indexed_chunk_count": len(records),
        "collection": vector_store_health().get("collection", ""),
    }
# Clears document vectors.
def clear_document_vectors(document_id: int) -> None:
    delete_document_vectors(document_id)


class _FastEmbedLangchainEmbeddings:
    """Adapter so LangChain retrievers reuse the project's FastEmbed functions."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return embed_query(text)


def _normalize_document_filters(
    *,
    document_id: int | None,
    document_ids: list[int] | None,
) -> list[int] | None:
    if document_id is not None:
        return [int(document_id)]
    if document_ids is None:
        return None
    normalized = [int(item) for item in document_ids]
    return normalized


def _build_chroma_where_filter(
    *,
    document_id: int | None,
    document_ids: list[int] | None,
    owner_user_id: int | None,
) -> dict[str, Any] | None:
    filters: list[dict[str, Any]] = []
    if document_id is not None:
        filters.append({"document_id": int(document_id)})
    elif document_ids is not None:
        if not document_ids:
            return {"document_id": -999999999}
        filters.append({"document_id": {"$in": [int(item) for item in document_ids]}})
    if owner_user_id is not None:
        filters.append({"owner_user_id": int(owner_user_id)})

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


def _search_vectors_with_langchain(
    query: str,
    *,
    limit: int,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    owner_user_id: int | None = None,
) -> list[dict[str, Any]] | None:
    try:
        from langchain_community.vectorstores import Chroma
    except Exception:
        return None

    where_filter = _build_chroma_where_filter(
        document_id=document_id,
        document_ids=document_ids,
        owner_user_id=owner_user_id,
    )
    if where_filter == {"document_id": -999999999}:
        return []

    vector_store = Chroma(
        client=get_chroma_client(),
        collection_name=vector_store_health().get("collection", ""),
        embedding_function=_FastEmbedLangchainEmbeddings(),
    )

    # Use LangChain built-in vector retrieval with explicit metadata filters.
    hits = vector_store.similarity_search_with_score(
        query=query,
        k=limit,
        filter=where_filter,
    )

    normalized_hits: list[dict[str, Any]] = []
    for doc, score in hits:
        metadata = doc.metadata or {}
        normalized_hits.append(
            {
                "id": str(metadata.get("id", "")),
                "score": float(score),
                "document_id": int(metadata.get("document_id", 0)),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "page_number": int(metadata.get("page_number", -1)),
                "owner_user_id": int(metadata.get("owner_user_id", -1)),
                "source_name": str(metadata.get("source_name", "")),
                "permissions_tags": str(metadata.get("permissions_tags", "[]")),
                "content": str(doc.page_content or ""),
            }
        )
    return normalized_hits


def _fetch_scoped_chunks(
    *,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    owner_user_id: int | None = None,
    limit: int | None = None,
) -> list[DocumentChunk]:
    statement = select(DocumentChunk)
    if document_id is not None:
        statement = statement.where(DocumentChunk.document_id == int(document_id))
    elif document_ids is not None:
        if not document_ids:
            return []
        statement = statement.where(DocumentChunk.document_id.in_([int(item) for item in document_ids]))
    if owner_user_id is not None:
        statement = statement.where(DocumentChunk.owner_user_id == int(owner_user_id))

    statement = statement.order_by(DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc())
    if limit is not None:
        statement = statement.limit(limit)

    with SessionLocal() as db:
        return list(db.scalars(statement).all())


def _chunk_to_payload(chunk: DocumentChunk, *, score: float, retrieval_method: str, rerank_score: float) -> dict[str, Any]:
    permissions_tags: list[str] = []
    try:
        parsed = json.loads(chunk.permissions_tags or "[]")
        if isinstance(parsed, list):
            permissions_tags = [tag for tag in parsed if isinstance(tag, str)]
    except json.JSONDecodeError:
        permissions_tags = []

    return {
        "id": str(chunk.id),
        "score": float(score),
        "document_id": int(chunk.document_id),
        "chunk_index": int(chunk.chunk_index),
        "page_number": chunk.page_number,
        "owner_user_id": chunk.owner_user_id,
        "source_name": chunk.source_name,
        "permissions_tags": permissions_tags,
        "content": chunk.content or "",
        "retrieval_method": retrieval_method,
        "rerank_score": float(rerank_score),
    }


def _build_bm25_retriever_from_chunks(chunks: list[DocumentChunk], *, k: int):
    try:
        from langchain_community.retrievers import BM25Retriever
        from langchain_core.documents import Document
    except Exception:
        return None

    documents = [
        Document(
            page_content=chunk.content or "",
            metadata={
                "id": str(chunk.id),
                "document_id": int(chunk.document_id),
                "chunk_index": int(chunk.chunk_index),
                "page_number": int(chunk.page_number if chunk.page_number is not None else -1),
                "owner_user_id": int(chunk.owner_user_id if chunk.owner_user_id is not None else -1),
                "source_name": chunk.source_name,
                "permissions_tags": chunk.permissions_tags or "[]",
            },
        )
        for chunk in chunks
        if (chunk.content or "").strip()
    ]
    if not documents:
        return None

    retriever = BM25Retriever.from_documents(documents)
    retriever.k = k
    return retriever


# Searches chunk text for the relevent documents
def search_chunk_text(
    query: str,
    *,
    limit: int,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    owner_user_id: int | None = None,
) -> list[dict[str, Any]]:
    scoped_document_ids = _normalize_document_filters(
        document_id=document_id,
        document_ids=document_ids,
    )
    if scoped_document_ids is not None and not scoped_document_ids:
        return []

    results = _search_vectors_with_langchain(
        query,
        limit=limit,
        document_id=document_id,
        document_ids=scoped_document_ids if document_id is None else None,
        owner_user_id=owner_user_id,
    )
    if results is None:
        # Fallback to direct Chroma query path if LangChain vectorstore isn't available.
        query_vector = embed_query(query)
        results = search_vectors(
            query_vector,
            limit=limit,
            document_id=document_id,
            document_ids=scoped_document_ids if document_id is None else None,
            owner_user_id=owner_user_id,
        )

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


# Runs keyword search across stored chunk text.
def keyword_search_chunk_text(
    query: str,
    *,
    limit: int,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    owner_user_id: int | None = None,
) -> list[dict[str, Any]]:
    chunks = _fetch_scoped_chunks(
        document_id=document_id,
        document_ids=document_ids,
        owner_user_id=owner_user_id,
        limit=max(limit * 50, limit),
    )
    if not chunks:
        return []

    bm25 = _build_bm25_retriever_from_chunks(chunks, k=limit)
    if bm25 is None:
        return []

    id_to_chunk = {str(chunk.id): chunk for chunk in chunks}
    hits = bm25.invoke(query)
    ranked: list[dict[str, Any]] = []
    for rank, doc in enumerate(hits, start=1):
        metadata = doc.metadata or {}
        chunk_id = str(metadata.get("id", ""))
        chunk = id_to_chunk.get(chunk_id)
        if chunk is None:
            continue
        ranked.append(
            _chunk_to_payload(
                chunk,
                score=float(rank),
                retrieval_method="keyword",
                rerank_score=1.0 / float(rank),
            )
        )
    return ranked[:limit]


def hybrid_search_chunk_text(
    query: str,
    *,
    limit: int,
    document_id: int | None = None,
    document_ids: list[int] | None = None,
    owner_user_id: int | None = None,
) -> dict[str, Any]:
    semantic_matches = search_chunk_text(
        query,
        limit=limit,
        document_id=document_id,
        document_ids=document_ids,
        owner_user_id=owner_user_id,
    )
    keyword_matches = keyword_search_chunk_text(
        query,
        limit=limit,
        document_id=document_id,
        document_ids=document_ids,
        owner_user_id=owner_user_id,
    )

    try:
        from langchain.retrievers import EnsembleRetriever
    except Exception:
        merged = {str(item["id"]): item for item in semantic_matches}
        for item in keyword_matches:
            merged.setdefault(str(item["id"]), item)
        ranked = list(merged.values())[:limit]
        return {
            "matches": ranked,
            "semantic_match_count": len(semantic_matches),
            "keyword_match_count": len(keyword_matches),
            "hybrid_match_count": len(ranked),
        }

    chunks = _fetch_scoped_chunks(
        document_id=document_id,
        document_ids=document_ids,
        owner_user_id=owner_user_id,
        limit=max(limit * 50, limit),
    )
    bm25 = _build_bm25_retriever_from_chunks(chunks, k=limit)

    where_filter = _build_chroma_where_filter(
        document_id=document_id,
        document_ids=document_ids,
        owner_user_id=owner_user_id,
    )
    try:
        from langchain_community.vectorstores import Chroma
        vector_store = Chroma(
            client=get_chroma_client(),
            collection_name=vector_store_health().get("collection", ""),
            embedding_function=_FastEmbedLangchainEmbeddings(),
        )
        semantic_retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": limit, "filter": where_filter},
        )
    except Exception:
        semantic_retriever = None

    if semantic_retriever is None or bm25 is None:
        merged = {str(item["id"]): item for item in semantic_matches}
        for item in keyword_matches:
            merged.setdefault(str(item["id"]), item)
        ranked = list(merged.values())[:limit]
        return {
            "matches": ranked,
            "semantic_match_count": len(semantic_matches),
            "keyword_match_count": len(keyword_matches),
            "hybrid_match_count": len(ranked),
        }

    ensemble = EnsembleRetriever(
        retrievers=[semantic_retriever, bm25],
        weights=[0.65, 0.35],
    )
    docs = ensemble.invoke(query)
    id_to_chunk = {str(chunk.id): chunk for chunk in chunks}
    seen: set[str] = set()
    ranked: list[dict[str, Any]] = []
    for rank, doc in enumerate(docs, start=1):
        metadata = doc.metadata or {}
        chunk_id = str(metadata.get("id", ""))
        if not chunk_id or chunk_id in seen:
            continue
        chunk = id_to_chunk.get(chunk_id)
        if chunk is None:
            continue
        seen.add(chunk_id)
        ranked.append(
            _chunk_to_payload(
                chunk,
                score=float(rank),
                retrieval_method="hybrid",
                rerank_score=1.0 / float(rank),
            )
        )
        if len(ranked) >= limit:
            break

    return {
        "matches": ranked,
        "semantic_match_count": len(semantic_matches),
        "keyword_match_count": len(keyword_matches),
        "hybrid_match_count": len(ranked),
    }


