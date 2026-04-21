"""
File purpose:
- Phase 3 chunking utilities for ingestion.
- Produces clean, overlap-aware chunks with metadata, ready for embeddings/retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(slots=True)
class ChunkingConfig:
    chunk_size: int = 900
    chunk_overlap: int = 150
    separators: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")


def _validate_config(config: ChunkingConfig) -> None:
    if config.chunk_size <= 0:
        raise ValueError("chunk_size must be > 0.")
    if config.chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0.")
    if config.chunk_overlap >= config.chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")


def _build_splitter(config: ChunkingConfig) -> RecursiveCharacterTextSplitter:
    _validate_config(config)
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=list(config.separators),
        length_function=len,
        is_separator_regex=False,
    )


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
    Chunk plain text into recursive overlap-aware chunks with metadata.
    """
    cfg = config or ChunkingConfig()
    splitter = _build_splitter(cfg)

    chunks = splitter.split_text(text or "")
    output: list[dict[str, Any]] = []

    for idx, chunk in enumerate(chunks):
        chunk_text_value = chunk.strip()
        if not chunk_text_value:
            continue

        output.append(
            {
                "chunk_id": uuid4().hex,
                "document_id": document_id,
                "source_name": source_name,
                "page_number": None,
                "chunk_index": idx,
                "owner_user_id": owner_user_id,
                "permissions_tags": permissions_tags or [],
                "content": chunk_text_value,
            }
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
    splitter = _build_splitter(cfg)

    output: list[dict[str, Any]] = []
    global_idx = 0

    for section in sections:
        section_text = section.get(text_key, "")
        if not isinstance(section_text, str) or not section_text.strip():
            continue

        page_number = section.get(page_key)
        section_chunks = splitter.split_text(section_text)

        for chunk in section_chunks:
            chunk_text_value = chunk.strip()
            if not chunk_text_value:
                continue

            output.append(
                {
                    "chunk_id": uuid4().hex,
                    "document_id": document_id,
                    "source_name": source_name,
                    "page_number": page_number,
                    "chunk_index": global_idx,
                    "owner_user_id": owner_user_id,
                    "permissions_tags": permissions_tags or [],
                    "content": chunk_text_value,
                }
            )
            global_idx += 1

    return output


def semantic_chunk_text(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """
    Placeholder for advanced semantic chunking.
    Keep this separate from recursive chunking for future Phase 3 upgrades.
    """
    raise NotImplementedError("Semantic chunking is not implemented yet.")

