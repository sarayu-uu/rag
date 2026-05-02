"""
File purpose:
- Phase 3 chunking utilities for ingestion.
- Produces semantic-style chunks with metadata, ready for embeddings/retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ChunkingConfig:
    chunk_size: int = 900
    chunk_overlap: int = 150


# Validates chunking settings before splitting text.
# Ensures chunk size is positive, overlap is non-negative,
# and overlap is smaller than chunk size.
def _validate_config(config: ChunkingConfig) -> None:
    if config.chunk_size <= 0:
        raise ValueError("chunk_size must be > 0.")
    if config.chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0.")
    if config.chunk_overlap >= config.chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")



# Creates one standardized chunk dictionary with all metadata fields
# (document id, chunk index, source/page info, owner, permissions, and content)
# so it can be stored consistently in DB/vector indexing flow.
def _make_chunk_record(
    *,
    document_id: int | None,
    source_name: str,
    page_number: int | None,
    chunk_index: int,
    owner_user_id: int | None,
    permissions_tags: list[str] | None,
    content: str,
) -> dict[str, Any]:
    return {
        "chunk_id": uuid4().hex,
        "document_id": document_id,
        "source_name": source_name,
        "page_number": page_number,
        "chunk_index": chunk_index,
        "owner_user_id": owner_user_id,
        "permissions_tags": permissions_tags or [],
        "content": content,
    }


# Split text into sentence-like units so chunks follow natural boundaries.
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE_SPLIT_PATTERN.split(text) if part.strip()]
    return parts if parts else ([text.strip()] if text.strip() else [])


# Builds semantic-ish chunks by grouping related sentence units until chunk_size.
# Overlap is applied as trailing characters from previous chunk for continuity.
def _split_semantic_text(text: str, config: ChunkingConfig) -> list[str]:
    _validate_config(config)
    text_value = (text or "").strip()
    if not text_value:
        return []

    semantic_units: list[str] = []
    for paragraph in [part.strip() for part in text_value.split("\n\n") if part.strip()]:
        semantic_units.extend(_split_sentences(paragraph))

    chunks: list[str] = []
    current = ""

    for unit in semantic_units:
        if not current:
            current = unit
            continue

        candidate = f"{current} {unit}".strip()
        if len(candidate) <= config.chunk_size:
            current = candidate
            continue

        chunks.append(current)
        overlap_tail = current[-config.chunk_overlap :].strip() if config.chunk_overlap > 0 else ""
        current = f"{overlap_tail} {unit}".strip() if overlap_tail else unit

        if len(current) > config.chunk_size:
            # Fallback for very large single sentence/unit.
            chunks.append(current[: config.chunk_size].strip())
            current = current[max(config.chunk_size - config.chunk_overlap, 1) :].strip()

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk]


# Detailed function explanation:
# - Purpose: `chunk_text` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def chunk_text(
    text: str,
    *,
    document_id: int | None = None,
    source_name: str = "",
    owner_user_id: int | None = None,
    permissions_tags: list[str] | None = None,
    config: ChunkingConfig | None = None,
) -> list[dict[str, Any]]:
    """
    Chunk plain text into semantic-style overlap-aware chunks with metadata.
    """
    cfg = config or ChunkingConfig()
    chunks = _split_semantic_text(text, cfg)
    output: list[dict[str, Any]] = []

    for idx, chunk in enumerate(chunks):
        chunk_text_value = chunk.strip()
        if not chunk_text_value:
            continue

        output.append(
            _make_chunk_record(
                document_id=document_id,
                source_name=source_name,
                page_number=None,
                chunk_index=idx,
                owner_user_id=owner_user_id,
                permissions_tags=permissions_tags,
                content=chunk_text_value,
            )
        )

    return output


# Detailed function explanation:
# - Purpose: `chunk_sections` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def chunk_sections(
    sections: list[dict[str, Any]],
    *,
    document_id: int | None = None,
    source_name: str = "",
    owner_user_id: int | None = None,
    permissions_tags: list[str] | None = None,
    text_key: str = "text",
    page_key: str = "page_number",
    config: ChunkingConfig | None = None,
) -> list[dict[str, Any]]:
    """
    Chunk page/section-based content while preserving page metadata per chunk.
    """
    cfg = config or ChunkingConfig()

    output: list[dict[str, Any]] = []
    global_idx = 0

    for section in sections:
        section_text = section.get(text_key, "")
        if not isinstance(section_text, str) or not section_text.strip():
            continue

        page_number = section.get(page_key)
        section_chunks = _split_semantic_text(section_text, cfg)

        for chunk in section_chunks:
            chunk_text_value = chunk.strip()
            if not chunk_text_value:
                continue

            output.append(
                _make_chunk_record(
                    document_id=document_id,
                    source_name=source_name,
                    page_number=page_number,
                    chunk_index=global_idx,
                    owner_user_id=owner_user_id,
                    permissions_tags=permissions_tags,
                    content=chunk_text_value,
                )
            )
            global_idx += 1

    return output


