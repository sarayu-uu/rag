"""
File purpose:
- Exposes step-by-step ingestion endpoints for debugging and demo in Swagger.
- Steps: load (raw extraction), clean (text cleaning), chunk (chunk generation).
- Also provides upload endpoints that can store chunks in MySQL and Chroma.
- In normal app flow, the frontend mainly uses `/documents/upload`, while this file
  is most useful for debugging or running ingestion step by step.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import shutil
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.security import get_current_user, is_privileged_user
from app.config.settings import UPLOAD_DIR
from app.ingestion.chunking import (
    ChunkingConfig,
    chunk_sections,
    chunk_text,
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
from app.models.mysql import Document, DocumentStatus, User, get_db, get_or_create_default_ingestion_user
from app.retrieval.service import sync_document_chunks_to_vector_store

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
    chunk_size: int = Field(default=500, description="Maximum chunk length before splitting.")
    chunk_overlap: int = Field(default=100, description="Character overlap between adjacent chunks.")


# Cleans the incoming URL value from form data.
# It turns placeholder values like "string" or empty input into `None`.
# Normalizes url input into a consistent format.
def _normalize_url_input(url: str | None) -> str | None:
    if url is None:
        return None
    value = url.strip()
    if value.lower() in {"", "string", "none", "null"}:
        return None
    return value


# Saves the uploaded file into the uploads folder.
# It also validates file size and returns the saved path, size, and safe filename.
# Saves upload.
def _save_upload(file: UploadFile, ext: str) -> tuple[Path, int, str]:
    file_size = validate_file_size(file)
    safe_name = f"{Path(file.filename).stem}_{uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path, file_size, safe_name


# Makes sure the request contains exactly one source:
# either a file or a URL, but not both.
def _single_input_guard(file: UploadFile | None, url: str | None) -> None:
    if (file is None and not url) or (file is not None and url):
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one input: either 'file' or 'url'.",
        )


def _compute_file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _compute_text_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _find_duplicate_document_id(
    db: Session,
    *,
    upload_user_id: int,
    file_hash: str,
) -> int | None:
    if not hasattr(Document, "file_hash"):
        return None

    duplicate_id = db.scalar(
        select(Document.id).where(
            Document.upload_user_id == int(upload_user_id),
            Document.file_hash == file_hash,
        )
    )
    return int(duplicate_id) if duplicate_id is not None else None


# Validates chunk size and overlap from form input.
# Returns a `ChunkingConfig` object if the values are valid.
# Validates chunk form inputs before the next step.
def _validate_chunk_form_inputs(chunk_size: int, chunk_overlap: int) -> ChunkingConfig:
    if chunk_size <= 0:
        raise HTTPException(status_code=400, detail="chunk_size must be > 0.")
    if chunk_overlap < 0:
        raise HTTPException(status_code=400, detail="chunk_overlap must be >= 0.")
    if chunk_overlap >= chunk_size:
        raise HTTPException(status_code=400, detail="chunk_overlap must be smaller than chunk_size.")
    return ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


# Reads `permissions_tags` from form input.
# Accepts JSON arrays or simple comma-separated text and returns a clean list of tags.
# Parses permissions tags.
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


# Converts stored permissions JSON text back into a Python list.
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


# Chunks one cleaned text string into chunk records.
# This path is used for non-PDF inputs or whenever page-wise chunking is not needed.
# Chunks cleaned text.
def _chunk_cleaned_text(
    cleaned_text: str,
    *,
    document_id: int,
    source_name: str,
    owner_user_id: int | None,
    permissions_tags: list[str],
    config: ChunkingConfig,
) -> list[dict[str, Any]]:
    validate_extracted_content(cleaned_text)
    #here chunk text is called
    return chunk_text(
        cleaned_text,
        document_id=document_id,
        source_name=source_name,
        owner_user_id=owner_user_id,
        permissions_tags=permissions_tags,
        config=config,
    )


# Chunks a PDF document page by page.
# It reloads PDF sections, cleans each page, and preserves page numbers in chunk metadata.
# Chunks pdf document.
def _chunk_pdf_document(
    document: Document,
    *,
    source_name: str,
    owner_user_id: int | None,
    permissions_tags: list[str],
    config: ChunkingConfig,
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

    return chunk_sections(
        sections,
        document_id=document.id,
        source_name=source_name,
        owner_user_id=owner_user_id,
        permissions_tags=permissions_tags,
        config=config,
    )


# Chooses the right chunking path for a document.
# PDFs use page-aware chunking, while other sources use normal text chunking.
# Builds chunks for document for the next step.
def _build_chunks_for_document(
    document: Document,
    *,
    cleaned_text: str,
    source_name: str,
    owner_user_id: int | None,
    permissions_tags: list[str],
    config: ChunkingConfig,
) -> list[dict[str, Any]]:
    # if pdf then one chunking
    if document.file_type.lower() == "pdf" and Path(document.storage_path).exists():
        return _chunk_pdf_document(
            document,
            source_name=source_name,
            owner_user_id=owner_user_id,
            permissions_tags=permissions_tags,
            config=config,
        )
    # if not pdf then other chunking
    return _chunk_cleaned_text(
        cleaned_text,
        document_id=document.id,
        source_name=source_name,
        owner_user_id=owner_user_id,
        permissions_tags=permissions_tags,
        config=config,
    )


# Loads one document from MySQL and raises `404` if it does not exist
# or the current user is not allowed to access it.
# Gets document or 404.
def _get_document_or_404(db: Session, document_id: int, *, current_user: User | None = None) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=404, detail=f"document_id {document_id} was not found.")
    if current_user is not None and not is_privileged_user(current_user) and document.upload_user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"document_id {document_id} was not found.")
    return document


# Converts saved chunk ORM objects into plain dictionaries
# so they can be returned cleanly in API responses.
# Converts chunks into a response-friendly format.
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


# Sends saved chunks to the vector DB for indexing.
# If indexing fails, it raises a clear API error explaining the document was saved in MySQL first.
def _index_saved_chunks(document_id: int, saved_chunks: list[Any]) -> dict[str, Any]:
    try:
        #saves the embedings in the vector db
        return sync_document_chunks_to_vector_store(saved_chunks)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Document {document_id} was saved in MySQL, but Chroma indexing failed: {exc}. "
                "Use /retrieval/reindex/{document_id} after fixing the vector-store issue."
            ),
        ) from exc


@router.post(
    "/load",
    summary="Step 1: Load input and extract raw text",
    description=(
        "Debug endpoint `/ingestion/load`. "
        "Use it to extract raw text and create an initial document record without running the full pipeline."
    ),
)
# Step 1 of the debug ingestion flow.
# It loads a file or URL, extracts raw text, and creates the first document row in MySQL.
def step_load(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    url = _normalize_url_input(url)
    _single_input_guard(file, url)
    upload_user = current_user if current_user is not None else get_or_create_default_ingestion_user(db)

    if url:
        try:
            result = load_url_with_metadata(url)
            raw_text = result["text"]
            metadata = result["metadata"]
            validate_extracted_content(raw_text)
            url_hash = _compute_text_sha256(raw_text)
            duplicate_id = _find_duplicate_document_id(
                db,
                upload_user_id=upload_user.id,
                file_hash=url_hash,
            )
            if duplicate_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate content detected. Existing document_id: {duplicate_id}.",
                )
            document_payload = build_document_record_payload(
                source="url",
                storage_path=url,
                file_type=metadata["file_type"],
                upload_user_id=upload_user.id,
                source_url=url,
                file_hash=url_hash,
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
        file_hash = _compute_file_sha256(file_path)
        duplicate_id = _find_duplicate_document_id(
            db,
            upload_user_id=upload_user.id,
            file_hash=file_hash,
        )
        if duplicate_id is not None:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate content detected. Existing document_id: {duplicate_id}.",
            )
        result = load_file_with_metadata(file_path, document_name=Path(file.filename).name)
        raw_text = result["text"]
        metadata = result["metadata"]
        validate_extracted_content(raw_text)
        document_payload = build_document_record_payload(
            source="file",
            storage_path=str(file_path),
            file_type=metadata["file_type"],
            upload_user_id=upload_user.id,
            source_url=None,
            file_hash=file_hash,
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


# Builds the final API response for upload endpoints.
# It packages document info, previews, chunk counts, and optional vector-index details.
# Builds upload response for the next step.
def _build_upload_response(
    *,
    document: Document,
    source: str,
    metadata: dict[str, Any],
    raw_text: str,
    cleaned_text: str,
    saved_chunks: list[Any],
    vector_collection: str | None = None,
    vector_indexed: bool = False,
) -> dict[str, Any]:
    pipeline_trace = [
        "validate_file_type -> app.ingestion.validators.validate_file_type",
        "validate_file_size -> app.ingestion.validators.validate_file_size",
        "load/extract -> app.ingestion.router.load_file_with_metadata|load_url_with_metadata",
        "content_validate_raw -> app.ingestion.validators.validate_extracted_content",
        "clean_text -> app.ingestion.text_cleaning.clean_text",
        "content_validate_cleaned -> app.ingestion.validators.validate_extracted_content",
        "chunking -> app.ingestion.chunking.chunk_text|chunk_sections (LangChain RecursiveCharacterTextSplitter with fallback)",
        "persist_chunks -> app.ingestion.document_record.replace_document_chunks",
    ]
    if vector_indexed:
        pipeline_trace.append("embed+index -> app.retrieval.service.sync_document_chunks_to_vector_store")

    return {
        "status": "success",
        "source": source,
        "document_id": document.id,
        "upload_user_id": document.upload_user_id,
        "metadata": metadata,
        "raw_text_preview": raw_text[:1200],
        "cleaned_text_preview": cleaned_text[:1200],
        "chunking_strategy": "semantic",
        "chunk_count": len(saved_chunks),
        "vector_indexed": vector_indexed,
        "vector_collection": vector_collection,
        "chunks": _serialize_chunks(saved_chunks),
        "pipeline_trace": pipeline_trace,
    }


# Runs the full ingestion pipeline in one place:
# load -> validate -> clean -> chunk -> save in MySQL -> optionally index in Chroma.
# Runs upload pipeline.
def _run_upload_pipeline(
    *,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    permissions_tags: str | None = Form(default=None),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
    index_in_vector_store: bool,
    upload_user: User | None = None,
) -> dict[str, Any]:
    url = _normalize_url_input(url) #cleans the url
    _single_input_guard(file, url) #cheks if user gave only one source
    #below forms chunkconfig
    config = _validate_chunk_form_inputs(chunk_size, chunk_overlap)
    #if any perimissions are given
    parsed_permissions_tags = _parse_permissions_tags(permissions_tags)
    # if users is not created then create one
    effective_upload_user = upload_user if upload_user is not None else get_or_create_default_ingestion_user(db)

    if url:
        try:
            result = load_url_with_metadata(url)
            raw_text = result["text"]
            metadata = result["metadata"]
            validate_extracted_content(raw_text)
            cleaned_text = clean_text(raw_text)
            validate_extracted_content(cleaned_text)
            url_hash = _compute_text_sha256(cleaned_text)
            duplicate_id = _find_duplicate_document_id(
                db,
                upload_user_id=effective_upload_user.id,
                file_hash=url_hash,
            )
            if duplicate_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate content detected. Existing document_id: {duplicate_id}.",
                )

            document_payload = build_document_record_payload(
                source="url",
                storage_path=url,
                file_type=metadata["file_type"],
                upload_user_id=effective_upload_user.id,
                source_url=url,
                file_hash=url_hash,
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

        if index_in_vector_store:
            index_result = _index_saved_chunks(document.id, saved_chunks)
            response = _build_upload_response(
                document=document,
                source="url",
                metadata=metadata,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                saved_chunks=saved_chunks,
                vector_collection=index_result.get("collection"),
                vector_indexed=True,
            )
            response["message"] = "Load, cleaning, chunking, and Chroma indexing completed."
            return response

        response = _build_upload_response(
            document=document,
            source="url",
            metadata=metadata,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            saved_chunks=saved_chunks,
        )
        response["message"] = "Load, cleaning, and chunking completed."
        return response

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file received.")

    ext = validate_file_type(file.filename) #validating file type
    #check file size and save uplaod in uploads folder
    file_path, file_size, safe_name = _save_upload(file, ext)
    try:
        file_hash = _compute_file_sha256(file_path) # create file hash
        duplicate_id = _find_duplicate_document_id( # check fr duplicate files
            db,
            upload_user_id=effective_upload_user.id,
            file_hash=file_hash,
        )
        if duplicate_id is not None: #throw error if duplicate file exsists
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate content detected. Existing document_id: {duplicate_id}.",
            )
        # this is used to find the extenstion to extract text
        result = load_file_with_metadata(file_path, document_name=Path(file.filename).name)
        raw_text = result["text"]
        metadata = result["metadata"]
        validate_extracted_content(raw_text)
        cleaned_text = clean_text(raw_text)
        validate_extracted_content(cleaned_text)
        # build document to save it in mysql
        document_payload = build_document_record_payload(
            source="file",
            storage_path=str(file_path),
            file_type=metadata["file_type"],
            upload_user_id=effective_upload_user.id,
            source_url=None,
            file_hash=file_hash,
            document_name=metadata["document_name"],
            page_numbers=metadata["page_numbers"],
        )
        #saving it in mysql
        document = save_document_record(db, document_payload)
        # used for chunking
        chunks = _build_chunks_for_document(
            document,
            cleaned_text=cleaned_text,
            source_name=document.title,
            owner_user_id=document.upload_user_id,
            permissions_tags=parsed_permissions_tags,
            config=config,
        ) # from this the chunks will be outputted
        # chunks saved in mysql in document_chunks
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

    final_metadata = {
        **metadata,
        "stored_as": safe_name,
        "size_bytes": file_size,
    }

    if index_in_vector_store:
        # to convert chunks into embeddings and store them using 
        # upsert_chunk_vectors
        index_result = _index_saved_chunks(document.id, saved_chunks)
        # create response so store in doucment_chunks
        response = _build_upload_response(
            document=document,
            source="file",
            metadata=final_metadata,
            raw_text=raw_text,
            cleaned_text=cleaned_text,
            saved_chunks=saved_chunks,
            vector_collection=index_result.get("collection"),
            vector_indexed=True,
        )
        response["message"] = "Load, cleaning, chunking, and Chroma indexing completed."
        return response

    response = _build_upload_response(
        document=document,
        source="file",
        metadata=final_metadata,
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        saved_chunks=saved_chunks,
    )
    response["message"] = "Load, cleaning, and chunking completed."
    return response


@router.post(
    "/uploadtochunk",
    summary="Step 1 to 3: Load, clean, and chunk in one request",
    description=(
        "Debug endpoint `/ingestion/uploadtochunk`. "
        "Runs load + clean + chunk and saves chunks in MySQL without vector indexing."
    ),
)
# Debug upload flow that stops before vector indexing.
# Useful when you want to inspect cleaned text and stored chunks first.
# Uploads to chunk.
def upload_to_chunk(
    response: Response,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    permissions_tags: str | None = Form(default=None),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    started = perf_counter()
    payload = _run_upload_pipeline(
        file=file,
        url=url,
        permissions_tags=permissions_tags,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        db=db,
        index_in_vector_store=False,
        upload_user=current_user,
    )
    if response is not None:
        response.headers["X-Telemetry-Ingestion-Time-Ms"] = str(int((perf_counter() - started) * 1000))
    return payload


@router.post(
    "/upload",
    summary="Default upload: store document, chunks, and vectors automatically",
    description=(
        "Usable endpoint `/ingestion/upload`. "
        "Runs the full ingestion flow and stores chunks in MySQL and Chroma."
    ),
)
# Full ingestion endpoint in this route file.
# It saves the document, creates chunks, and indexes them in the vector DB.
# Uploads document.
def upload_document(
    response: Response,
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    permissions_tags: str | None = Form(default=None),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    started = perf_counter()
    payload = _run_upload_pipeline(
        file=file,
        url=url,
        permissions_tags=permissions_tags,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        db=db,
        index_in_vector_store=True,
        upload_user=current_user,
    )
    if response is not None:
        response.headers["X-Telemetry-Ingestion-Time-Ms"] = str(int((perf_counter() - started) * 1000))
    return payload


@router.post(
    "/upload-batch",
    summary="Batch upload: store multiple documents, chunks, and vectors",
    description=(
        "Usable endpoint `/ingestion/upload-batch`. "
        "Processes multiple uploaded files in one request and indexes each successful document."
    ),
)
# Batch version of the upload pipeline.
# It loops through many files and returns which ones succeeded or failed.
# Uploads documents batch.
def upload_documents_batch(
    response: Response,
    files: list[UploadFile] = File(default_factory=list),
    permissions_tags: str | None = Form(default=None),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    started = perf_counter()
    if not files:
        raise HTTPException(status_code=400, detail="No files received. Use form field name 'files'.")

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
            )
            results.append(
                {
                    "file_name": filename,
                    "status": "success",
                    "document_id": pipeline_result.get("document_id"),
                    "chunk_count": pipeline_result.get("chunk_count", 0),
                    "vector_indexed": pipeline_result.get("vector_indexed", False),
                    "message": pipeline_result.get("message"),
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

    payload = {
        "status": "success" if failure_count == 0 else "partial_success",
        "total_files": len(files),
        "processed_files": success_count + failure_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
    }
    if response is not None:
        response.headers["X-Telemetry-Ingestion-Time-Ms"] = str(int((perf_counter() - started) * 1000))
    return payload


@router.post(
    "/clean",
    summary="Step 2: Clean and normalize extracted text",
    description="Debug endpoint `/ingestion/clean`. Cleans extracted text before chunking.",
)
# Step 2 of the debug ingestion flow.
# It cleans extracted text and returns the cleaned result.
def step_clean(
    payload: CleanTextRequest,
    _: User = Depends(get_current_user),
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


@router.post(
    "/chunk",
    summary="Step 3: Chunk cleaned text with metadata",
    description=(
        "Debug endpoint `/ingestion/chunk`. "
        "Chunks cleaned text, saves chunk rows, and indexes them in the vector DB."
    ),
)
# Step 3 of the debug ingestion flow.
# It takes cleaned text, turns it into chunks, saves them, and indexes them.
def step_chunk(
    payload: ChunkTextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    config = _validate_chunk_form_inputs(payload.chunk_size, payload.chunk_overlap)
    document = _get_document_or_404(db, payload.document_id, current_user=current_user)
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
        )
        saved_chunks = replace_document_chunks(db, document_id=document.id, chunks=chunks)
        document.status = DocumentStatus.PROCESSED
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to persist document chunks in MySQL.",
        ) from exc

    index_result = _index_saved_chunks(document.id, saved_chunks)

    return {
        "status": "success",
        "message": "Chunking completed, stored in MySQL, and indexed in Chroma.",
        "source": "text",
        "document_id": document.id,
        "chunking_strategy": "semantic",
        "chunk_count": len(saved_chunks),
        "vector_indexed": True,
        "vector_collection": index_result.get("collection"),
        "cleaned_text_preview": payload.text[:1200],
        "chunks": _serialize_chunks(saved_chunks),
    }

