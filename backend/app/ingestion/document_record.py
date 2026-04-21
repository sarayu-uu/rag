"""
File purpose:
- Prepares document metadata payloads for database persistence.
- Includes a DB-write helper that is ready but not invoked yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.mysql import Document


def build_document_record_payload(
    *,
    source: str,
    storage_path: str,
    file_type: str,
    upload_user_id: int | None,
    source_url: str | None,
    page_numbers: list[int] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    source_name = source_url if source == "url" else Path(storage_path).name

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

    document = Document(
        title=payload["title"],
        file_type=payload["file_type"],
        storage_path=payload["storage_path"],
        source_url=payload.get("source_url"),
        upload_user_id=payload["upload_user_id"],
        status=payload.get("status", "uploaded"),
    )

    db.add(document)
    db.flush()
    return document

