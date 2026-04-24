"""
File purpose:
- Phase 3 chunking utilities for ingestion.
- Produces simple fixed-size chunks with metadata, ready for embeddings/retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ChunkingConfig:
    chunk_size: int = 900
    chunk_overlap: int = 150


def _validate_config(config: ChunkingConfig) -> None:
    if config.chunk_size <= 0:
        raise ValueError("chunk_size must be > 0.")
    if config.chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0.")
    if config.chunk_overlap >= config.chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")


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


def _split_fixed_text(text: str, config: ChunkingConfig) -> list[str]:
    _validate_config(config)
    text_value = (text or "").strip()
    if not text_value:
        return []

    chunks: list[str] = []
    step = config.chunk_size - config.chunk_overlap
    for start in range(0, len(text_value), step):
        chunk = text_value[start : start + config.chunk_size].strip()
        if chunk:
            chunks.append(chunk)

    return chunks


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
    Chunk plain text into fixed-size overlap-aware chunks with metadata.
    """
    cfg = config or ChunkingConfig()
    chunks = _split_fixed_text(text, cfg)
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
        section_chunks = _split_fixed_text(section_text, cfg)

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


