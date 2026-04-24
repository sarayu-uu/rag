"""
File purpose:
- Exposes document-level CRUD endpoints for frontend use.
- Reuses the existing ingestion upload pipeline for document creation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.mysql import Document, DocumentChunk, get_db
from app.retrieval.service import clear_document_vectors
from app.routes.ingestion_steps import _run_upload_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])


def _serialize_document(document: Document, chunk_count: int) -> dict[str, Any]:
    return {
        "id": document.id,
        "title": document.title,
        "file_type": document.file_type,
        "storage_path": document.storage_path,
        "source_url": document.source_url,
        "upload_user_id": document.upload_user_id,
        "status": document.status.value,
        "uploaded_at": document.uploaded_at.isoformat(),
        "chunk_count": chunk_count,
    }


def _get_document_with_chunk_count(db: Session, document_id: int) -> tuple[Document, int] | None:
    row = db.execute(
        select(Document, func.count(DocumentChunk.id))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.id == document_id)
        .group_by(Document.id)
    ).first()
    if row is None:
        return None
    return row[0], int(row[1] or 0)


@router.post("/upload", summary="Phase 12: Upload a document through the default ingestion pipeline")
def upload_document(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    permissions_tags: str | None = Form(default=None),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _run_upload_pipeline(
        file=file,
        url=url,
        permissions_tags=permissions_tags,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        db=db,
        index_in_vector_store=True,
    )


@router.get("", summary="Phase 12: List stored documents")
def list_documents(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(
        select(Document, func.count(DocumentChunk.id))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.uploaded_at.desc(), Document.id.desc())
    ).all()

    documents = [_serialize_document(document, int(chunk_count or 0)) for document, chunk_count in rows]
    return {
        "status": "success",
        "count": len(documents),
        "documents": documents,
    }


@router.get("/{document_id}", summary="Phase 12: Get one stored document")
def get_document(document_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = _get_document_with_chunk_count(db, document_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found.")

    document, chunk_count = payload
    return {
        "status": "success",
        "document": _serialize_document(document, chunk_count),
    }


@router.delete("/{document_id}", summary="Phase 12: Delete a stored document and its vectors")
def delete_document(document_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = _get_document_with_chunk_count(db, document_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found.")

    document, chunk_count = payload
    try:
        clear_document_vectors(document.id)
        db.delete(document)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete the document from MySQL.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Failed to delete vectors for document {document.id}: {exc}") from exc

    return {
        "status": "success",
        "message": "Document deleted successfully.",
        "document": _serialize_document(document, chunk_count),
    }
