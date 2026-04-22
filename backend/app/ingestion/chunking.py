"""
File purpose:
- Phase 3 chunking utilities for ingestion.
- Produces clean, overlap-aware chunks with metadata, ready for embeddings/retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
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


def _split_semantic_units(text: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", text) if paragraph.strip()]
    if not paragraphs:
        return []

    units: list[str] = []
    for paragraph in paragraphs:
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", paragraph) if sentence.strip()]
        if len(sentences) <= 1:
            units.append(paragraph)
            continue
        units.extend(sentences)
    return units


def _group_units_with_overlap(units: list[str], config: ChunkingConfig) -> list[str]:
    _validate_config(config)
    if not units:
        return []

    chunks: list[str] = []
    current_units: list[str] = []
    current_length = 0

    for unit in units:
        separator_length = 1 if current_units else 0
        projected_length = current_length + separator_length + len(unit)
        if current_units and projected_length > config.chunk_size:
            chunk_text_value = " ".join(current_units).strip()
            if chunk_text_value:
                chunks.append(chunk_text_value)

            overlap_units: list[str] = []
            overlap_length = 0
            for previous_unit in reversed(current_units):
                added_length = len(previous_unit) + (1 if overlap_units else 0)
                if overlap_units and overlap_length >= config.chunk_overlap:
                    break
                overlap_units.insert(0, previous_unit)
                overlap_length += added_length

            current_units = overlap_units[:]
            current_length = len(" ".join(current_units)) if current_units else 0

        current_units.append(unit)
        current_length = len(" ".join(current_units))

    final_chunk = " ".join(current_units).strip()
    if final_chunk:
        chunks.append(final_chunk)

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


def semantic_chunk_text(
    text: str,
    *,
    document_id: int | None = None,
    source_name: str = "",
    owner_user_id: int | None = None,
    permissions_tags: list[str] | None = None,
    config: ChunkingConfig | None = None,
) -> list[dict[str, Any]]:
    """
    Chunk text by grouping paragraph and sentence units instead of arbitrary character cuts.
    """
    cfg = config or ChunkingConfig()
    units = _split_semantic_units(text or "")
    chunks = _group_units_with_overlap(units, cfg)

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


def semantic_chunk_sections(
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
    Semantic chunking that preserves section/page metadata.
    """
    cfg = config or ChunkingConfig()
    output: list[dict[str, Any]] = []
    global_idx = 0

    for section in sections:
        section_text = section.get(text_key, "")
        if not isinstance(section_text, str) or not section_text.strip():
            continue

        page_number = section.get(page_key)
        section_chunks = _group_units_with_overlap(_split_semantic_units(section_text), cfg)

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

