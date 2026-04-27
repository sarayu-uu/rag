"""
File purpose:
- Exposes Phase 4 retrieval endpoints for vector search and reindexing.
- Helps verify that vector indexing is working before Phase 5 RAG generation.
"""

from __future__ import annotations

from time import perf_counter

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user, is_privileged_user
from app.models.mysql import Document, DocumentChunk, User, get_db
from app.retrieval.service import (
    ensure_vector_store_ready,
    search_chunk_text,
    sync_document_chunks_to_vector_store,
)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


class RetrievalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language query to search against indexed chunks.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of similar chunks to return.")


@router.post("/search", summary="Phase 4: Search indexed chunks in the vector store")
def search_indexed_chunks(
    payload: RetrievalSearchRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> dict:
    retrieval_start = perf_counter()
    try:
        ensure_vector_store_ready()
        matches = search_chunk_text(
            payload.query,
            limit=payload.limit,
            owner_user_id=None if is_privileged_user(current_user) else current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vector store retrieval failed: {exc}") from exc

    response.headers["X-Telemetry-Retrieval-Latency-Ms"] = str(int((perf_counter() - retrieval_start) * 1000))

    return {
        "status": "success",
        "query": payload.query,
        "match_count": len(matches),
        "matches": matches,
    }


@router.post("/reindex/{document_id}", summary="Phase 4: Reindex one document into the vector store")
def reindex_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail=f"document_id {document_id} was not found.")
    if not is_privileged_user(current_user) and document.upload_user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"document_id {document_id} was not found.")

    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        ).all()
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="This document has no chunks to index.")

    try:
        ensure_vector_store_ready()
        result = sync_document_chunks_to_vector_store(chunks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Vector store reindex failed: {exc}") from exc

    return {
        "status": "success",
        "document_id": document.id,
        "title": document.title,
        **result,
    }
