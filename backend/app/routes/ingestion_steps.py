"""
File purpose:
- Exposes step-by-step ingestion endpoints for debugging and demo in Swagger.
- Steps: load (raw extraction), clean (text cleaning), chunk (chunk generation).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import shutil
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.settings import UPLOAD_DIR
from app.ingestion.chunking import (
    ChunkingConfig,
    chunk_sections,
    chunk_text,
    semantic_chunk_sections,
    semantic_chunk_text,
)
from app.ingestion.document_record import (
    build_document_record_payload,
    replace_document_chunks,
    save_document_record,
)
from app.ingestion.router import load_file_with_metadata, load_url_with_metadata
from app.ingestion.loaders import load_pdf_sections
from app.ingestion.text_cleaning import clean_text
from app.ingestion.validators import (
    validate_extracted_content,
    validate_file_size,
    validate_file_type,
)
from app.models.mysql import Document, DocumentStatus, get_db, get_or_create_default_ingestion_user

router = APIRouter(prefix="/ingestion", tags=["ingestion-steps"])
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class CleanTextRequest(BaseModel):
    document_id: int = Field(..., gt=0, description="Document id returned by /ingestion/load.")
    text: str = Field(..., description="Raw extracted text returned by /ingestion/load.")


class ChunkTextRequest(BaseModel):
    document_id: int = Field(..., gt=0, description="Document id returned by /ingestion/load.")
    text: str = Field(..., description="Cleaned text returned by /ingestion/clean.")
    source_name: str = Field(default="", description="Optional source label stored with each chunk.")
    owner_user_id: int | None = Field(default=None, description="Optional owner id stored with each chunk.")
    permissions_tags: list[str] = Field(default_factory=list, description="Optional permission tags for chunk metadata.")
    chunking_strategy: str = Field(default="recursive", description="Choose 'recursive' or 'semantic' chunking.")
    chunk_size: int = Field(default=500, description="Maximum chunk length before splitting.")
    chunk_overlap: int = Field(default=100, description="Character overlap between adjacent chunks.")


def _normalize_url_input(url: str | None) -> str | None:
    if url is None:
        return None
    value = url.strip()
    if value.lower() in {"", "string", "none", "null"}:
        return None
    return value


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


def _validate_chunk_form_inputs(chunk_size: int, chunk_overlap: int) -> ChunkingConfig:
    if chunk_size <= 0:
        raise HTTPException(status_code=400, detail="chunk_size must be > 0.")
    if chunk_overlap < 0:
        raise HTTPException(status_code=400, detail="chunk_overlap must be >= 0.")
    if chunk_overlap >= chunk_size:
        raise HTTPException(status_code=400, detail="chunk_overlap must be smaller than chunk_size.")
    return ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def _resolve_chunking_strategy(strategy: str) -> str:
    normalized = strategy.strip().lower()
    if normalized not in {"recursive", "semantic"}:
        raise HTTPException(status_code=400, detail="chunking_strategy must be 'recursive' or 'semantic'.")
    return normalized


def _parse_permissions_tags(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []

    value = raw_value.strip()
    if not value or value.lower() in {"string", "null", "none", "[]"}:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        # Swagger form inputs are easier to use if we also accept "tag1,tag2"
        # or a single plain-text tag instead of forcing strict JSON.
        fallback_tags = [tag.strip() for tag in value.split(",") if tag.strip()]
        if fallback_tags:
            return fallback_tags
        raise HTTPException(status_code=400, detail="permissions_tags must be valid JSON or comma-separated text.") from exc

    if not isinstance(parsed, list) or not all(isinstance(tag, str) for tag in parsed):
        raise HTTPException(status_code=400, detail="permissions_tags must be a JSON array of strings.")
    return [tag.strip() for tag in parsed if tag.strip()]


def _deserialize_permissions_tags(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [tag for tag in parsed if isinstance(tag, str)]


def _chunk_cleaned_text(
    cleaned_text: str,
    *,
    document_id: int,
    source_name: str,
    owner_user_id: int | None,
    permissions_tags: list[str],
    config: ChunkingConfig,
    strategy: str,
) -> list[dict[str, Any]]:
    validate_extracted_content(cleaned_text)
    if strategy == "semantic":
        return semantic_chunk_text(
            cleaned_text,
            document_id=document_id,
            source_name=source_name,
            owner_user_id=owner_user_id,
            permissions_tags=permissions_tags,
            config=config,
        )
    return chunk_text(
        cleaned_text,
        document_id=document_id,
        source_name=source_name,
        owner_user_id=owner_user_id,
        permissions_tags=permissions_tags,
        config=config,
    )


def _chunk_pdf_document(
    document: Document,
    *,
    source_name: str,
    owner_user_id: int | None,
    permissions_tags: list[str],
    config: ChunkingConfig,
    strategy: str,
) -> list[dict[str, Any]]:
    sections = [
        {
            "page_number": int(section["page_number"]),
            "text": clean_text(str(section["text"])),
        }
        for section in load_pdf_sections(document.storage_path)
    ]
    sections = [section for section in sections if section["text"].strip()]
    if not sections:
        raise ValueError("No meaningful text could be extracted from this PDF.")

    if strategy == "semantic":
        return semantic_chunk_sections(
            sections,
            document_id=document.id,
            source_name=source_name,
            owner_user_id=owner_user_id,
            permissions_tags=permissions_tags,
            config=config,
        )
    return chunk_sections(
        sections,
        document_id=document.id,
        source_name=source_name,
        owner_user_id=owner_user_id,
        permissions_tags=permissions_tags,
        config=config,
    )


def _build_chunks_for_document(
    document: Document,
    *,
    cleaned_text: str,
    source_name: str,
    owner_user_id: int | None,
    permissions_tags: list[str],
    config: ChunkingConfig,
    strategy: str,
) -> list[dict[str, Any]]:
    if document.file_type.lower() == "pdf" and Path(document.storage_path).exists():
        return _chunk_pdf_document(
            document,
            source_name=source_name,
            owner_user_id=owner_user_id,
            permissions_tags=permissions_tags,
            config=config,
            strategy=strategy,
        )

    return _chunk_cleaned_text(
        cleaned_text,
        document_id=document.id,
        source_name=source_name,
        owner_user_id=owner_user_id,
        permissions_tags=permissions_tags,
        config=config,
        strategy=strategy,
    )


def _get_document_or_404(db: Session, document_id: int) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail=f"document_id {document_id} was not found.")
    return document


def _serialize_chunks(chunks: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": chunk.id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "page_number": chunk.page_number,
            "source_name": chunk.source_name,
            "owner_user_id": chunk.owner_user_id,
            "permissions_tags": _deserialize_permissions_tags(chunk.permissions_tags),
            "created_at": chunk.created_at.isoformat(),
        }
        for chunk in chunks
    ]


@router.post("/load", summary="Step 1: Load input and extract raw text")
async def step_load(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    url = _normalize_url_input(url)
    _single_input_guard(file, url)
    default_user = get_or_create_default_ingestion_user(db)

    if url:
        try:
            result = load_url_with_metadata(url)
            raw_text = result["text"]
            metadata = result["metadata"]
            validate_extracted_content(raw_text)
            document_payload = build_document_record_payload(
                source="url",
                storage_path=url,
                file_type=metadata["file_type"],
                upload_user_id=default_user.id,
                source_url=url,
                document_name=metadata["document_name"],
                page_numbers=metadata["page_numbers"],
            )
            document = save_document_record(db, document_payload)
            db.commit()
            db.refresh(document)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to persist the document record for the loaded URL.",
            ) from exc

        return {
            "status": "success",
            "message": "Raw text extraction completed.",
            "source": "url",
            "metadata": metadata,
            "document_id": document.id,
            "upload_user_id": document.upload_user_id,
            "raw_text": raw_text,
            "raw_text_preview": raw_text[:1200],
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    ext = validate_file_type(file.filename)
    file_path, file_size, safe_name = _save_upload(file, ext)
    try:
        result = load_file_with_metadata(file_path, document_name=Path(file.filename).name)
        raw_text = result["text"]
        metadata = result["metadata"]
        validate_extracted_content(raw_text)
        document_payload = build_document_record_payload(
            source="file",
            storage_path=str(file_path),
            file_type=metadata["file_type"],
            upload_user_id=default_user.id,
            source_url=None,
            document_name=metadata["document_name"],
            page_numbers=metadata["page_numbers"],
        )
        document = save_document_record(db, document_payload)
        db.commit()
        db.refresh(document)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to persist the document record for the loaded file.",
        ) from exc

    return {
        "status": "success",
        "message": "Raw text extraction completed.",
        "source": "file",
        "metadata": {
            **metadata,
            "stored_as": safe_name,
            "size_bytes": file_size,
        },
        "document_id": document.id,
        "upload_user_id": document.upload_user_id,
        "raw_text": raw_text,
        "raw_text_preview": raw_text[:1200],
    }


@router.post("/uploadtochunk", summary="Step 1 to 3: Load, clean, and chunk in one request")
async def upload_to_chunk(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    permissions_tags: str | None = Form(default=None),
    chunking_strategy: str = Form(default="recursive"),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    url = _normalize_url_input(url)
    _single_input_guard(file, url)
    config = _validate_chunk_form_inputs(chunk_size, chunk_overlap)
    strategy = _resolve_chunking_strategy(chunking_strategy)
    parsed_permissions_tags = _parse_permissions_tags(permissions_tags)
    default_user = get_or_create_default_ingestion_user(db)

    if url:
        try:
            result = load_url_with_metadata(url)
            raw_text = result["text"]
            metadata = result["metadata"]
            validate_extracted_content(raw_text)
            cleaned_text = clean_text(raw_text)
            validate_extracted_content(cleaned_text)

            document_payload = build_document_record_payload(
                source="url",
                storage_path=url,
                file_type=metadata["file_type"],
                upload_user_id=default_user.id,
                source_url=url,
                document_name=metadata["document_name"],
                page_numbers=metadata["page_numbers"],
            )
            document = save_document_record(db, document_payload)
            chunks = _build_chunks_for_document(
                document,
                cleaned_text=cleaned_text,
                source_name=document.title,
                owner_user_id=document.upload_user_id,
                permissions_tags=parsed_permissions_tags,
                config=config,
                strategy=strategy,
            )
            saved_chunks = replace_document_chunks(db, document_id=document.id, chunks=chunks)
            document.status = DocumentStatus.PROCESSED
            db.commit()
            db.refresh(document)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to complete the load-clean-chunk pipeline for the URL.",
            ) from exc

        return {
            "status": "success",
            "message": "Load, cleaning, and chunking completed.",
            "source": "url",
            "document_id": document.id,
            "upload_user_id": document.upload_user_id,
            "metadata": metadata,
            "raw_text_preview": raw_text[:1200],
            "cleaned_text_preview": cleaned_text[:1200],
            "chunking_strategy": strategy,
            "chunk_count": len(saved_chunks),
            "chunks": _serialize_chunks(saved_chunks),
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    ext = validate_file_type(file.filename)
    file_path, file_size, safe_name = _save_upload(file, ext)
    try:
        result = load_file_with_metadata(file_path, document_name=Path(file.filename).name)
        raw_text = result["text"]
        metadata = result["metadata"]
        validate_extracted_content(raw_text)
        cleaned_text = clean_text(raw_text)
        validate_extracted_content(cleaned_text)

        document_payload = build_document_record_payload(
            source="file",
            storage_path=str(file_path),
            file_type=metadata["file_type"],
            upload_user_id=default_user.id,
            source_url=None,
            document_name=metadata["document_name"],
            page_numbers=metadata["page_numbers"],
        )
        document = save_document_record(db, document_payload)
        chunks = _build_chunks_for_document(
            document,
            cleaned_text=cleaned_text,
            source_name=document.title,
            owner_user_id=document.upload_user_id,
            permissions_tags=parsed_permissions_tags,
            config=config,
            strategy=strategy,
        )
        saved_chunks = replace_document_chunks(db, document_id=document.id, chunks=chunks)
        document.status = DocumentStatus.PROCESSED
        db.commit()
        db.refresh(document)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to complete the load-clean-chunk pipeline for the file.",
        ) from exc

    return {
        "status": "success",
        "message": "Load, cleaning, and chunking completed.",
        "source": "file",
        "document_id": document.id,
        "upload_user_id": document.upload_user_id,
        "metadata": {
            **metadata,
            "stored_as": safe_name,
            "size_bytes": file_size,
        },
        "raw_text_preview": raw_text[:1200],
        "cleaned_text_preview": cleaned_text[:1200],
        "chunking_strategy": strategy,
        "chunk_count": len(saved_chunks),
        "chunks": _serialize_chunks(saved_chunks),
    }


@router.post("/clean", summary="Step 2: Clean and normalize extracted text")
async def step_clean(
    payload: CleanTextRequest,
) -> dict[str, Any]:
    cleaned = clean_text(payload.text)
    validate_extracted_content(cleaned)
    return {
        "status": "success",
        "message": "Text cleaning completed.",
        "source": "text",
        "document_id": payload.document_id,
        "cleaned_text_preview": cleaned[:1200],
        "cleaned_text": cleaned,
    }


@router.post("/chunk", summary="Step 3: Chunk cleaned text with metadata")
async def step_chunk(
    payload: ChunkTextRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    config = _validate_chunk_form_inputs(payload.chunk_size, payload.chunk_overlap)
    strategy = _resolve_chunking_strategy(payload.chunking_strategy)
    document = _get_document_or_404(db, payload.document_id)
    source_name = payload.source_name.strip() or document.title
    owner_user_id = payload.owner_user_id if payload.owner_user_id is not None else document.upload_user_id

    try:
        chunks = _build_chunks_for_document(
            document,
            cleaned_text=payload.text,
            source_name=source_name,
            owner_user_id=owner_user_id,
            permissions_tags=payload.permissions_tags,
            config=config,
            strategy=strategy,
        )
        saved_chunks = replace_document_chunks(db, document_id=document.id, chunks=chunks)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to persist document chunks in MySQL.",
        ) from exc

    return {
        "status": "success",
        "message": "Chunking completed and chunks stored in MySQL.",
        "source": "text",
        "document_id": document.id,
        "chunking_strategy": strategy,
        "chunk_count": len(saved_chunks),
        "cleaned_text_preview": payload.text[:1200],
        "chunks": _serialize_chunks(saved_chunks),
    }
