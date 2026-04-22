"""
File purpose:
- Prepares document metadata payloads for database persistence.
- Includes a DB-write helper that is ready but not invoked yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.mysql import Document, DocumentChunk, DocumentStatus


def build_document_record_payload(
    *,
    source: str,
    storage_path: str,
    file_type: str,
    upload_user_id: int | None,
    source_url: str | None,
    document_name: str | None = None,
    page_numbers: list[int] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    if source == "url":
        source_name = document_name or source_url or storage_path
    else:
        source_name = document_name or Path(storage_path).name

    return {
        "title": source_name,
        "file_type": file_type,
        "storage_path": storage_path,
        "source_url": source_url,
        "upload_user_id": upload_user_id,
        "uploaded_at": now.isoformat(),
        "status": "uploaded",
        "page_numbers": page_numbers or [],
    }


def save_document_record(db: Session, payload: dict[str, Any]) -> Document:
    """
    DB-ready helper for when DB integration is enabled.
    Not called by the ingestion route yet.
    """
    if payload.get("upload_user_id") is None:
        raise ValueError("upload_user_id is required to persist documents in MySQL.")

    status_value = payload.get("status", DocumentStatus.UPLOADED.value)
    if isinstance(status_value, DocumentStatus):
        status = status_value
    else:
        status = DocumentStatus(str(status_value))

    document = Document(
        title=payload["title"],
        file_type=payload["file_type"],
        storage_path=payload["storage_path"],
        source_url=payload.get("source_url"),
        upload_user_id=payload["upload_user_id"],
        status=status,
    )

    db.add(document)
    db.flush()
    return document


def replace_document_chunks(
    db: Session,
    *,
    document_id: int,
    chunks: list[dict[str, Any]],
) -> list[DocumentChunk]:
    """
    Replace all stored chunks for a document with the latest chunk output.
    """
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

    saved_chunks: list[DocumentChunk] = []
    for chunk in chunks:
        document_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=int(chunk["chunk_index"]),
            content=str(chunk["content"]),
            page_number=chunk.get("page_number"),
            source_name=str(chunk.get("source_name") or ""),
            owner_user_id=chunk.get("owner_user_id"),
            permissions_tags=json.dumps(chunk.get("permissions_tags") or []),
        )
        db.add(document_chunk)
        saved_chunks.append(document_chunk)

    db.flush()
    return saved_chunks

