"""
File purpose:
- Defines upload API endpoints.
- Handles file or URL ingestion and returns extracted text preview.
"""

from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import shutil
from uuid import uuid4

from app.ingestion.router import load_file_with_metadata, load_url_with_metadata
from app.ingestion.validators import (
    validate_extracted_content,
    validate_file_size,
    validate_file_type,
)
from app.ingestion.document_record import build_document_record_payload
from app.config.settings import UPLOAD_DIR

router = APIRouter(tags=["ingestion"])
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_url_input(url: str | None) -> str | None:
    if url is None:
        return None
    value = url.strip()
    if value.lower() in {"", "string", "none", "null"}:
        return None
    return value


@router.post("/upload")
async def upload_file(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    upload_user_id: int | None = Form(default=None),
):
    url = _normalize_url_input(url)
    if (file is None and not url) or (file is not None and url):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one input: either 'file' or 'url'.",
        )

    if url:
        try:
            result = load_url_with_metadata(url)
            text = result["text"]
            metadata = result["metadata"]
            validate_extracted_content(text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        document_record = build_document_record_payload(
            source="url",
            storage_path=url,
            file_type=metadata["file_type"],
            upload_user_id=upload_user_id,
            source_url=url,
            page_numbers=metadata["page_numbers"],
        )

        return {
            "status": "success",
            "message": "URL load completed successfully",
            "source": "url",
            "text_preview": text[:500],
            "metadata": {
                **metadata,
                "upload_user_id": upload_user_id,
                "upload_time": document_record["uploaded_at"],
            },
            "document_record_preview": document_record,
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    ext = validate_file_type(file.filename)
    file_size = validate_file_size(file)

    safe_name = f"{Path(file.filename).stem}_{uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = load_file_with_metadata(file_path)
        text = result["text"]
        metadata = result["metadata"]
        validate_extracted_content(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    document_record = build_document_record_payload(
        source="file",
        storage_path=str(file_path),
        file_type=metadata["file_type"],
        upload_user_id=upload_user_id,
        source_url=None,
        page_numbers=metadata["page_numbers"],
    )

    return {
        "status": "success",
        "message": "Load completed successfully",
        "source": "file",
        "text_preview": text[:500],
        "metadata": {
            **metadata,
            "upload_user_id": upload_user_id,
            "upload_time": document_record["uploaded_at"],
            "size_bytes": file_size,
            "stored_as": safe_name,
        },
        "document_record_preview": document_record,
    }
