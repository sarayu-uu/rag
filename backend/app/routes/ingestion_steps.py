"""
File purpose:
- Exposes step-by-step ingestion endpoints for debugging and demo in Swagger.
- Steps: load (raw extraction), clean (text cleaning), chunk (chunk generation).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import shutil
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config.settings import UPLOAD_DIR
from app.ingestion.chunking import ChunkingConfig, chunk_sections, chunk_text
from app.ingestion.loaders import (
    load_csv,
    load_docx,
    load_image,
    load_json,
    load_pdf_sections,
    load_pptx,
    load_web,
)
from app.ingestion.text_cleaning import clean_sections, clean_text
from app.ingestion.validators import (
    validate_extracted_content,
    validate_file_size,
    validate_file_type,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion-steps"])
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_url_input(url: str | None) -> str | None:
    if url is None:
        return None
    value = url.strip()
    if value.lower() in {"", "string", "none", "null"}:
        return None
    return value


def _extract_raw_file(file_path: Path, ext: str) -> dict[str, Any]:
    if ext == ".pdf":
        sections = [
            {"page_number": int(sec["page_number"]), "text": str(sec["text"])}
            for sec in load_pdf_sections(file_path)
        ]
        text = "\n".join(section["text"] for section in sections)
        return {"text": text, "sections": sections}

    if ext == ".docx":
        return {"text": load_docx(file_path), "sections": []}
    if ext == ".pptx":
        return {"text": load_pptx(file_path), "sections": []}
    if ext in {".png", ".jpg", ".jpeg"}:
        return {"text": load_image(file_path), "sections": []}
    if ext == ".csv":
        return {"text": load_csv(file_path), "sections": []}
    if ext == ".json":
        return {"text": load_json(file_path), "sections": []}

    raise ValueError(f"Unsupported file type: {ext}")


def _extract_raw_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL. Please provide a full http/https URL.")
    return {"text": load_web(url), "sections": []}


def _save_upload(file: UploadFile, ext: str) -> tuple[Path, int, str]:
    file_size = validate_file_size(file)
    safe_name = f"{Path(file.filename).stem}_{uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path, file_size, safe_name


def _single_input_guard(file: UploadFile | None, url: str | None) -> None:
    if (file is None and not url) or (file is not None and url):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one input: either 'file' or 'url'.",
        )


@router.post("/load", summary="Step 1: Load input and extract raw text")
async def step_load(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
) -> dict[str, Any]:
    url = _normalize_url_input(url)
    _single_input_guard(file, url)

    if url:
        extracted = _extract_raw_url(url)
        validate_extracted_content(extracted["text"])
        return {
            "status": "success",
            "message": "Raw text extraction completed.",
            "source": "url",
            "metadata": {
                "document_name": urlparse(url).netloc,
                "file_type": "url",
                "source_url": url,
                "page_numbers": [],
            },
            "raw_text_preview": extracted["text"][:1200],
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    ext = validate_file_type(file.filename)
    file_path, file_size, safe_name = _save_upload(file, ext)
    extracted = _extract_raw_file(file_path, ext)
    validate_extracted_content(extracted["text"])

    page_numbers = [s["page_number"] for s in extracted["sections"] if s.get("text")] if extracted["sections"] else []

    return {
        "status": "success",
        "message": "Raw text extraction completed.",
        "source": "file",
        "metadata": {
            "document_name": Path(file.filename).name,
            "file_type": ext.lstrip("."),
            "stored_as": safe_name,
            "size_bytes": file_size,
            "page_numbers": page_numbers,
        },
        "raw_text_preview": extracted["text"][:1200],
    }


@router.post("/clean", summary="Step 2: Clean and normalize extracted text")
async def step_clean(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
) -> dict[str, Any]:
    url = _normalize_url_input(url)
    _single_input_guard(file, url)

    if url:
        extracted = _extract_raw_url(url)
        cleaned = clean_text(extracted["text"])
        validate_extracted_content(cleaned)
        return {
            "status": "success",
            "message": "Text cleaning completed.",
            "source": "url",
            "cleaned_text_preview": cleaned[:1200],
            "cleaned_text": cleaned,
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    ext = validate_file_type(file.filename)
    file_path, _, _ = _save_upload(file, ext)
    extracted = _extract_raw_file(file_path, ext)

    if extracted["sections"]:
        cleaned_sections = clean_sections(extracted["sections"], text_key="text")
        cleaned = "\n".join(section["text"] for section in cleaned_sections)
    else:
        cleaned = clean_text(extracted["text"])

    validate_extracted_content(cleaned)
    return {
        "status": "success",
        "message": "Text cleaning completed.",
        "source": "file",
        "cleaned_text_preview": cleaned[:1200],
        "cleaned_text": cleaned,
    }


@router.post("/chunk", summary="Step 3: Chunk cleaned text with metadata")
async def step_chunk(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    upload_user_id: int | None = Form(default=None),
    document_id: int | None = Form(default=None),
    chunk_size: int = Form(default=900),
    chunk_overlap: int = Form(default=150),
) -> dict[str, Any]:
    url = _normalize_url_input(url)
    _single_input_guard(file, url)
    config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if url:
        extracted = _extract_raw_url(url)
        cleaned = clean_text(extracted["text"])
        validate_extracted_content(cleaned)
        chunks = chunk_text(
            cleaned,
            document_id=document_id,
            source_name=url,
            owner_user_id=upload_user_id,
            permissions_tags=[],
            config=config,
        )
        return {
            "status": "success",
            "message": "Chunking completed.",
            "source": "url",
            "chunk_count": len(chunks),
            "chunks": chunks,
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    ext = validate_file_type(file.filename)
    file_path, _, _ = _save_upload(file, ext)
    extracted = _extract_raw_file(file_path, ext)
    source_name = Path(file.filename).name

    if extracted["sections"]:
        cleaned_sections = clean_sections(extracted["sections"], text_key="text")
        chunks = chunk_sections(
            cleaned_sections,
            document_id=document_id,
            source_name=source_name,
            owner_user_id=upload_user_id,
            permissions_tags=[],
            text_key="text",
            page_key="page_number",
            config=config,
        )
    else:
        cleaned = clean_text(extracted["text"])
        validate_extracted_content(cleaned)
        chunks = chunk_text(
            cleaned,
            document_id=document_id,
            source_name=source_name,
            owner_user_id=upload_user_id,
            permissions_tags=[],
            config=config,
        )

    return {
        "status": "success",
        "message": "Chunking completed.",
        "source": "file",
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
