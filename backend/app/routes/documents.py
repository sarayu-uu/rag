"""
File purpose:
- Exposes document-level CRUD endpoints for frontend use.
- Reuses the existing ingestion upload pipeline for document creation.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.auth.permissions import document_access_filter
from app.auth.security import get_current_user, is_privileged_user
from app.models.mysql import Document, DocumentChunk, Permission, User, get_db
from app.retrieval.service import clear_document_vectors
from app.routes.ingestion_steps import _run_upload_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])
# Converts document into a response-friendly format.
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
# Gets document with chunk count.
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
# Uploads document.
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


@router.post(
    "/upload-batch",
    summary="Phase 12: Upload multiple documents through the default ingestion pipeline",
    description=(
        "Usage: Used by frontend multi-file upload. "
        "Purpose: ingest, chunk, persist, and index each file independently with its own document id."
    ),
)
def upload_documents_batch(
    files: list[UploadFile] = File(default_factory=list),
    permissions_tags: str | None = Form(default=None),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files received. Use form field name 'files'.")

    started = perf_counter()
    results: list[dict[str, Any]] = []
    success_count = 0
    failure_count = 0

    for file in files:
        filename = file.filename or "unknown"
        try:
            pipeline_result = _run_upload_pipeline(
                file=file,
                url=None,
                permissions_tags=permissions_tags,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                db=db,
                index_in_vector_store=True,
                upload_user=current_user,
            )
            results.append(
                {
                    "file_name": filename,
                    "status": "success",
                    "document_id": pipeline_result.get("document_id"),
                    "chunk_count": pipeline_result.get("chunk_count", 0),
                    "vector_indexed": pipeline_result.get("vector_indexed", False),
                    "message": pipeline_result.get("message"),
                    "pipeline_trace": pipeline_result.get("pipeline_trace", []),
                }
            )
            success_count += 1
        except HTTPException as exc:
            db.rollback()
            results.append(
                {
                    "file_name": filename,
                    "status": "failed",
                    "detail": str(exc.detail),
                    "status_code": exc.status_code,
                }
            )
            failure_count += 1
        except Exception as exc:
            db.rollback()
            results.append(
                {
                    "file_name": filename,
                    "status": "failed",
                    "detail": str(exc),
                    "status_code": 500,
                }
            )
            failure_count += 1

    return {
        "status": "success" if failure_count == 0 else "partial_success",
        "total_files": len(files),
        "processed_files": success_count + failure_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "duration_ms": int((perf_counter() - started) * 1000),
        "results": results,
        "message": "Batch upload completed. Each successful file has its own document_id.",
    }


@router.get(
    "",
    summary="Phase 12: List stored documents",
    description="Usage: Used by frontend documents page. Purpose: returns accessible documents with chunk counts.",
)
# Lists documents.
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
# Gets document.
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


@router.get(
    "/{document_id}/view",
    summary="Phase 12: View one stored document",
    description="Usage: Used by frontend documents page. Purpose: opens a readable/downloadable view of one accessible document.",
)
def view_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = _get_document_with_chunk_count(db, document_id, current_user=current_user)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found.")

    document, _ = payload
    if document.source_url:
        return RedirectResponse(url=document.source_url)

    file_path = Path(document.storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored file path was not found on disk.")

    media_type = None
    if document.file_type:
        ext = document.file_type.lower()
        media_type_map = {
            "pdf": "application/pdf",
            "txt": "text/plain",
            "json": "application/json",
            "xml": "application/xml",
            "csv": "text/csv",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        media_type = media_type_map.get(ext)

    return FileResponse(
        path=str(file_path),
        filename=document.title or file_path.name,
        media_type=media_type,
    )


@router.delete(
    "/{document_id}",
    summary="Phase 12: Delete a stored document and its vectors",
    description="Usage: Used by frontend document actions. Purpose: removes the document from MySQL and vector store.",
)
# Deletes document.
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
        # Explicitly delete dependent rows to support older DB schemas
        # that may not have ON DELETE CASCADE constraints applied.
        db.execute(delete(Permission).where(Permission.document_id == document.id))
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.delete(document)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete the document from MySQL: {exc}") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Failed to delete vectors for document {document.id}: {exc}") from exc

    return {
        "status": "success",
        "message": "Document deleted successfully.",
        "document": _serialize_document(document, chunk_count),
        "pipeline_trace": [
            "vector_delete -> app.retrieval.service.clear_document_vectors",
            "mysql_delete_permissions -> sqlalchemy delete(Permission)",
            "mysql_delete_chunks -> sqlalchemy delete(DocumentChunk)",
            "mysql_delete_document -> sqlalchemy session.delete(Document)",
        ],
    }


