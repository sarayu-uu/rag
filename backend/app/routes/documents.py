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
from sqlalchemy.orm import Session, joinedload

from app.auth.permissions import document_access_filter
from app.auth.security import get_current_user, is_privileged_user
from app.models.mysql import Document, DocumentChunk, User, get_db
from app.retrieval.service import clear_document_vectors
from app.routes.ingestion_steps import _run_upload_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])


# Detailed function explanation:
# - Purpose: `_serialize_document` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _serialize_document(document: Document, chunk_count: int) -> dict[str, Any]:
    uploader_payload: dict[str, Any] | None = None
    if getattr(document, "uploader", None) is not None:
        uploader_payload = {
            "id": document.uploader.id,
            "name": document.uploader.username,
            "position": document.uploader.role.name.value if document.uploader.role else None,
        }

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
        "uploader": uploader_payload,
    }


# Detailed function explanation:
# - Purpose: `_get_document_with_chunk_count` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _get_document_with_chunk_count(
    db: Session,
    document_id: int,
    *,
    current_user: User,
    permission_field: str = "can_read",
) -> tuple[Document, int] | None:
    statement = (
        select(Document, func.count(DocumentChunk.id))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.id == document_id)
        .group_by(Document.id)
    )
    access_filter = document_access_filter(current_user, permission_field=permission_field)
    if access_filter is not None:
        statement = statement.where(access_filter)

    row = db.execute(statement).first()
    if row is None:
        return None
    return row[0], int(row[1] or 0)


@router.post(
    "/upload",
    summary="Phase 12: Upload a document through the default ingestion pipeline",
    description="Usage: Used by frontend document upload. Purpose: ingest, chunk, persist, and index one file or URL.",
)
# Detailed function explanation:
# - Purpose: `upload_document` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def upload_document(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    permissions_tags: str | None = Form(default=None),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return _run_upload_pipeline(
        file=file,
        url=url,
        permissions_tags=permissions_tags,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        db=db,
        index_in_vector_store=True,
        upload_user=current_user,
    )


@router.get(
    "",
    summary="Phase 12: List stored documents",
    description="Usage: Used by frontend documents page. Purpose: returns accessible documents with chunk counts.",
)
# Detailed function explanation:
# - Purpose: `list_documents` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    statement = (
        select(Document, func.count(DocumentChunk.id))
        .options(joinedload(Document.uploader).joinedload(User.role))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.uploaded_at.desc(), Document.id.desc())
    )
    access_filter = document_access_filter(current_user, permission_field="can_read")
    if access_filter is not None:
        statement = statement.where(access_filter)

    rows = db.execute(statement).all()

    include_uploader = is_privileged_user(current_user)
    documents = []
    for document, chunk_count in rows:
        payload = _serialize_document(document, int(chunk_count or 0))
        if not include_uploader:
            payload["uploader"] = None
        documents.append(payload)
    return {
        "status": "success",
        "count": len(documents),
        "documents": documents,
    }


@router.get(
    "/{document_id}",
    summary="Phase 12: Get one stored document",
    description="Usage: Used by frontend document details. Purpose: fetches one accessible document and metadata.",
)
# Detailed function explanation:
# - Purpose: `get_document` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    payload = _get_document_with_chunk_count(db, document_id, current_user=current_user)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found.")

    document, chunk_count = payload
    return {
        "status": "success",
        "document": _serialize_document(document, chunk_count),
    }


@router.delete(
    "/{document_id}",
    summary="Phase 12: Delete a stored document and its vectors",
    description="Usage: Used by frontend document actions. Purpose: removes the document from MySQL and vector store.",
)
# Detailed function explanation:
# - Purpose: `delete_document` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    payload = _get_document_with_chunk_count(
        db,
        document_id,
        current_user=current_user,
        permission_field="can_edit",
    )
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found or u dont havr the access to delete it.")

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
