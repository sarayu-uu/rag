"""
File purpose:
- Input validation helpers for ingestion endpoints.
- Validates file type, size, and extracted content quality.
"""

from __future__ import annotations

from pathlib import Path
from fastapi import HTTPException, UploadFile

from app.config.settings import MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".csv", ".json", ".xml"}


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_file_type(filename: str) -> str:
    ext = get_extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {ext or 'unknown'}. "
                f"Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )
    return ext


def validate_file_size(upload: UploadFile) -> int:
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)

    if size <= 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max allowed size is {MAX_UPLOAD_SIZE_MB} MB.",
        )

    return size


def validate_extracted_content(text: str) -> None:
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No meaningful text could be extracted from this input.",
        )
