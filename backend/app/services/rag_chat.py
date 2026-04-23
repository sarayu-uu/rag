"""
File purpose:
- Builds grounded RAG answers from retrieved chunk matches and user questions.
- Provides helpers for direct answer generation and retrieval + generation flows.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from langchain_core.messages import HumanMessage, SystemMessage

from app.retrieval.service import keyword_search_chunk_text, search_chunk_text
from app.services.chatgroq_bot import build_chat_model

MAX_CONTEXT_CHARS = 12000
OVERFETCH_MULTIPLIER = 3
SEMANTIC_WEIGHT = 0.65
KEYWORD_WEIGHT = 0.35
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=1)
def _get_prompt_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render_prompt(template_name: str, **context: Any) -> str:
    template = _get_prompt_environment().get_template(template_name)
    return template.render(**context).strip()


def _normalize_match(match: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": str(match.get("id", index)),
        "score": float(match.get("score", 0.0)),
        "document_id": int(match.get("document_id", 0)),
        "chunk_index": int(match.get("chunk_index", 0)),
        "page_number": match.get("page_number"),
        "source_name": str(match.get("source_name", "unknown")),
        "content": str(match.get("content", "")).strip(),
        "retrieval_method": str(match.get("retrieval_method", "semantic")),
        "rerank_score": float(match.get("rerank_score", 0.0)),
    }


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
                "retrieval_method": match["retrieval_method"],
                "rerank_score": match["rerank_score"],
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


def _normalize_semantic_scores(matches: list[dict[str, Any]]) -> dict[str, float]:
    if not matches:
        return {}
    max_distance = max(match["score"] for match in matches) or 1.0
    normalized: dict[str, float] = {}
    for match in matches:
        # Lower Chroma distance is better, so invert into a similarity-like score.
        normalized[str(match["id"])] = max(0.0, 1.0 - (float(match["score"]) / max_distance))
    return normalized


def _normalize_keyword_scores(matches: list[dict[str, Any]]) -> dict[str, float]:
    if not matches:
        return {}
    max_score = max(match["score"] for match in matches) or 1.0
    normalized: dict[str, float] = {}
    for match in matches:
        normalized[str(match["id"])] = float(match["score"]) / max_score
    return normalized


def _rerank_hybrid_matches(
    semantic_matches: list[dict[str, Any]],
    keyword_matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    semantic_scores = _normalize_semantic_scores(semantic_matches)
    keyword_scores = _normalize_keyword_scores(keyword_matches)
    merged: dict[str, dict[str, Any]] = {}

    for match in semantic_matches:
        match_id = str(match["id"])
        merged[match_id] = {
            **match,
            "retrieval_method": "semantic",
            "semantic_score": semantic_scores.get(match_id, 0.0),
            "keyword_score": keyword_scores.get(match_id, 0.0),
        }

    for match in keyword_matches:
        match_id = str(match["id"])
        if match_id in merged:
            merged[match_id]["keyword_score"] = keyword_scores.get(match_id, 0.0)
            merged[match_id]["retrieval_method"] = "hybrid"
            continue

        merged[match_id] = {
            **match,
            "semantic_score": semantic_scores.get(match_id, 0.0),
            "keyword_score": keyword_scores.get(match_id, 0.0),
        }

    reranked: list[dict[str, Any]] = []
    for item in merged.values():
        content_bonus = min(len(item.get("content", "")) / 1000.0, 0.15)
        rerank_score = (
            item.get("semantic_score", 0.0) * SEMANTIC_WEIGHT
            + item.get("keyword_score", 0.0) * KEYWORD_WEIGHT
            + content_bonus
        )
        reranked.append(
            {
                **item,
                "rerank_score": rerank_score,
            }
        )

    reranked.sort(
        key=lambda item: (
            -item["rerank_score"],
            item["document_id"],
            item["chunk_index"],
        )
    )
    return reranked


def answer_question_from_matches(question: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question must not be empty.")

    normalized_matches = [_normalize_match(match, index) for index, match in enumerate(matches, start=1)]
    usable_matches = [match for match in normalized_matches if match["content"]]
    if not usable_matches:
        return {
            "answer": "The retrieved documents do not contain enough information to answer this confidently.",
            "sources": [],
            "documents_used": [],
            "match_count": 0,
        }

    system_prompt = _render_prompt("rag_system.jinja2")
    user_prompt = _render_prompt(
        "rag_user.jinja2",
        question=cleaned_question,
        matches=usable_matches,
    )

    response = build_chat_model().invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
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
    candidate_limit = max(limit * OVERFETCH_MULTIPLIER, limit)
    semantic_matches = search_chunk_text(question, limit=candidate_limit)
    keyword_matches = keyword_search_chunk_text(question, limit=candidate_limit)
    reranked_matches = _rerank_hybrid_matches(semantic_matches, keyword_matches)
    selected_matches = _select_multi_document_context(reranked_matches, limit=limit)
    result = answer_question_from_matches(question, selected_matches)
    result["matches"] = selected_matches
    result["retrieved_match_count"] = len(reranked_matches)
    result["retrieval_debug"] = {
        "semantic_match_count": len(semantic_matches),
        "keyword_match_count": len(keyword_matches),
        "hybrid_match_count": len(reranked_matches),
    }
    return result
