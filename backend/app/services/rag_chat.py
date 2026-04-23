"""
File purpose:
- Builds grounded RAG answers from retrieved chunk matches and user questions.
- Provides helpers for direct answer generation and retrieval + generation flows.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.retrieval.service import search_chunk_text
from app.services.chatgroq_bot import build_chat_model


RAG_SYSTEM_PROMPT = (
    "You are a retrieval-augmented assistant. Answer the user's question using only the "
    "provided document context when it is relevant. If the answer is not in the context, "
    "say that clearly. Do not invent facts. Include a short Sources section at the end "
    "that cites the source names and page numbers you used."
)


def _normalize_match(match: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": str(match.get("id", index)),
        "score": float(match.get("score", 0.0)),
        "document_id": int(match.get("document_id", 0)),
        "chunk_index": int(match.get("chunk_index", 0)),
        "page_number": match.get("page_number"),
        "source_name": str(match.get("source_name", "unknown")),
        "content": str(match.get("content", "")).strip(),
    }


def _build_context(matches: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, raw_match in enumerate(matches, start=1):
        match = _normalize_match(raw_match, index)
        page_label = match["page_number"] if match["page_number"] is not None else "unknown"
        blocks.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"source_name: {match['source_name']}",
                    f"document_id: {match['document_id']}",
                    f"chunk_index: {match['chunk_index']}",
                    f"page_number: {page_label}",
                    f"score: {match['score']}",
                    "content:",
                    match["content"],
                ]
            )
        )
    return "\n\n".join(blocks)


def _build_sources(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for index, raw_match in enumerate(matches, start=1):
        match = _normalize_match(raw_match, index)
        sources.append(
            {
                "label": f"Source {index}",
                "document_id": match["document_id"],
                "source_name": match["source_name"],
                "page_number": match["page_number"],
                "chunk_index": match["chunk_index"],
                "score": match["score"],
                "id": match["id"],
            }
        )
    return sources


def answer_question_from_matches(question: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question must not be empty.")

    normalized_matches = [_normalize_match(match, index) for index, match in enumerate(matches, start=1)]
    usable_matches = [match for match in normalized_matches if match["content"]]
    if not usable_matches:
        return {
            "answer": "I could not find any retrieved document context to answer that question.",
            "sources": [],
            "match_count": 0,
        }

    prompt = "\n\n".join(
        [
            f"User question:\n{cleaned_question}",
            "Retrieved document context:",
            _build_context(usable_matches),
            "Answer the question using only the retrieved context. If the answer is missing, say so.",
        ]
    )

    response = build_chat_model().invoke(
        [
            SystemMessage(content=RAG_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
    )
    answer = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "answer": answer,
        "sources": _build_sources(usable_matches),
        "match_count": len(usable_matches),
    }


def answer_question_with_retrieval(
    question: str,
    *,
    limit: int,
) -> dict[str, Any]:
    matches = search_chunk_text(question, limit=limit)
    result = answer_question_from_matches(question, matches)
    result["matches"] = matches
    return result
