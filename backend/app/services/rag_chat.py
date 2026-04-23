"""
File purpose:
- Builds grounded RAG answers from retrieved chunk matches and user questions.
- Provides helpers for direct answer generation and retrieval + generation flows.
"""

from __future__ import annotations

from collections import defaultdict
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
MAX_CONTEXT_CHARS = 12000
OVERFETCH_MULTIPLIER = 3


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


def _summarize_documents(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for match in matches:
        document_id = int(match["document_id"])
        summary = grouped.setdefault(
            document_id,
            {
                "document_id": document_id,
                "source_name": match["source_name"],
                "match_count": 0,
                "pages": set(),
                "best_score": match["score"],
            },
        )
        summary["match_count"] += 1
        if match["page_number"] is not None:
            summary["pages"].add(match["page_number"])
        summary["best_score"] = min(summary["best_score"], match["score"])

    return [
        {
            "document_id": summary["document_id"],
            "source_name": summary["source_name"],
            "match_count": summary["match_count"],
            "pages": sorted(summary["pages"]),
            "best_score": summary["best_score"],
        }
        for summary in sorted(grouped.values(), key=lambda item: (item["best_score"], item["document_id"]))
    ]


def _select_multi_document_context(matches: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        grouped[int(match["document_id"])].append(match)

    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    current_context_chars = 0

    # Round-robin selection spreads context across documents first.
    ordered_document_ids = sorted(
        grouped,
        key=lambda document_id: min(item["score"] for item in grouped[document_id]),
    )
    while len(selected) < limit:
        made_progress = False
        for document_id in ordered_document_ids:
            if not grouped[document_id]:
                continue

            candidate = grouped[document_id].pop(0)
            if candidate["id"] in seen_ids:
                continue

            candidate_size = len(candidate["content"])
            if selected and current_context_chars + candidate_size > MAX_CONTEXT_CHARS:
                continue

            selected.append(candidate)
            seen_ids.add(candidate["id"])
            current_context_chars += candidate_size
            made_progress = True

            if len(selected) >= limit:
                break

        if not made_progress:
            break

    return selected


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
        "documents_used": _summarize_documents(usable_matches),
        "match_count": len(usable_matches),
    }


def answer_question_with_retrieval(
    question: str,
    *,
    limit: int,
) -> dict[str, Any]:
    raw_matches = search_chunk_text(question, limit=max(limit * OVERFETCH_MULTIPLIER, limit))
    selected_matches = _select_multi_document_context(raw_matches, limit=limit)
    result = answer_question_from_matches(question, selected_matches)
    result["matches"] = selected_matches
    result["retrieved_match_count"] = len(raw_matches)
    return result
