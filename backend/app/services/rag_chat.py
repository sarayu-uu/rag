"""
File purpose:
- Builds grounded RAG answers from retrieved chunk matches and user questions.
- Provides helpers for direct answer generation and retrieval + generation flows.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from time import perf_counter
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langsmith import traceable

from app.retrieval.service import hybrid_search_chunk_text
from app.services.chatgroq_bot import build_chat_model

MAX_CONTEXT_CHARS = 12000
OVERFETCH_MULTIPLIER = 3
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i", "if", "in", "is",
    "it", "me", "of", "on", "or", "please", "show", "that", "the", "this", "to", "what", "when",
    "where", "which", "with", "you", "your",
}
MIN_RERANK_SCORE = 0.08
# Pulls token usage details from the model response.
def _extract_token_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


@lru_cache(maxsize=1)
# Gets prompt environment.
def _get_prompt_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
# Renders a prompt template with the current values.
def _render_prompt(template_name: str, **context: Any) -> str:
    template = _get_prompt_environment().get_template(template_name)
    return template.render(**context).strip()


@lru_cache(maxsize=1)
def _get_answer_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}"),
            ("human", "{user_prompt}"),
        ]
    )
    # LCEL chain: prompt formatting -> chat model invocation.
    return prompt | build_chat_model()
# Removes inline source labels from the answer text.
def _strip_inline_sources(answer: str) -> str:
    cleaned = (answer or "").strip()
    if not cleaned:
        return ""

    # Remove trailing "Sources:" / "Citations:" sections from model text output.
    cleaned = re.sub(
        r"(?is)\n\s*(sources?|citations?)\s*:\s*[\s\S]*$",
        "",
        cleaned,
    ).strip()
    return cleaned
# Normalizes memory context into a consistent format.
def _normalize_memory_context(memory_context: dict[str, Any] | None) -> dict[str, Any]:
    context = memory_context or {}
    older_summary = context.get("older_summary", "")
    recent_messages = context.get("recent_messages", [])
    message_count = context.get("message_count", len(recent_messages) if isinstance(recent_messages, list) else 0)
    return {
        "older_summary": str(older_summary or ""),
        "recent_messages": recent_messages if isinstance(recent_messages, list) else [],
        "message_count": int(message_count or 0),
    }
# Normalizes match into a consistent format.
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


def _extract_query_terms(question: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+", question.lower())
    terms = {token for token in tokens if len(token) > 2 and token not in STOP_WORDS}
    return terms


def _filter_relevant_matches(question: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = _extract_query_terms(question)
    if not terms:
        return matches

    filtered: list[dict[str, Any]] = []
    for match in matches:
        content = str(match.get("content", "")).lower()
        overlap = sum(1 for term in terms if term in content)
        if overlap > 0:
            filtered.append(match)

    # If filtering is too strict, fall back to original matches.
    return filtered if filtered else matches


def _build_formatting_instruction(question: str) -> str:
    text = question.lower()
    wants_code = any(keyword in text for keyword in {"code", "syntax", "snippet", "program", "example code"})
    wants_bullets = any(keyword in text for keyword in {"bullet", "points", "list", "steps"})

    if wants_code and wants_bullets:
        return "Use concise bullet points, and include code examples in fenced Markdown code blocks."
    if wants_code:
        return "If code is relevant, format it in fenced Markdown code blocks with a language tag."
    if wants_bullets:
        return "Format the answer as concise bullet points."
    return "Use clear paragraph format unless the user explicitly asks for a different structure."


def _build_prompt_payload(payload: dict[str, Any]) -> dict[str, str]:
    question = str(payload.get("question", "")).strip()
    matches = payload.get("usable_matches", [])
    memory_context = payload.get("memory_context")
    system_prompt = _render_prompt("rag_system.jinja2")
    user_prompt = _render_prompt(
        "rag_user.jinja2",
        question=question,
        matches=matches,
        memory_context=_normalize_memory_context(memory_context),
        formatting_instruction=_build_formatting_instruction(question),
    )
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }


def _extract_answer_payload(response: Any) -> str:
    answer = response.content if isinstance(response.content, str) else str(response.content)
    return _strip_inline_sources(answer)
# Builds sources for the next step.
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
# Builds a short summary of the retrieved documents.
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
# Chooses context chunks across multiple documents.
def _select_ranked_context(question: str, matches: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    # Keep only matches that look relevant enough.
    filtered = _filter_relevant_matches(question, matches)
    ranked = sorted(
        filtered,
        key=lambda item: (
            -float(item.get("rerank_score", 0.0)),
            float(item.get("score", 0.0)),
            int(item.get("chunk_index", 0)),
        ),
    )

    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    current_context_chars = 0
    for candidate in ranked:
        if candidate["id"] in seen_ids:
            continue
        if float(candidate.get("rerank_score", 0.0)) < MIN_RERANK_SCORE:
            continue
        candidate_size = len(candidate["content"])
        if selected and current_context_chars + candidate_size > MAX_CONTEXT_CHARS:
            continue
        selected.append(candidate)
        seen_ids.add(candidate["id"])
        current_context_chars += candidate_size
        if len(selected) >= limit:
            break

    # Fallback in case thresholding filtered out too much.
    if not selected:
        for candidate in ranked[:limit]:
            if candidate["id"] in seen_ids:
                continue
            selected.append(candidate)
            seen_ids.add(candidate["id"])
    return selected


@lru_cache(maxsize=1)
def _get_generation_chain():
    return RunnableLambda(_build_prompt_payload) | _get_answer_chain()


def _run_retrieval_step(payload: dict[str, Any]) -> dict[str, Any]:
    question = str(payload.get("question", "")).strip()
    limit = int(payload.get("limit", 5) or 5)
    candidate_limit = max(limit * OVERFETCH_MULTIPLIER, limit)
    retrieval_payload = hybrid_search_chunk_text(
        question,
        limit=candidate_limit,
        document_ids=payload.get("document_ids"),
        owner_user_id=payload.get("owner_user_id"),
    )
    reranked_matches = retrieval_payload.get("matches", [])
    selected_matches = _select_ranked_context(question, reranked_matches, limit=limit)
    return {
        **payload,
        "retrieval_payload": retrieval_payload,
        "reranked_matches": reranked_matches,
        "selected_matches": selected_matches,
    }


def _run_generation_step(payload: dict[str, Any]) -> dict[str, Any]:
    selected_matches = payload.get("selected_matches", [])
    model_start = perf_counter()
    response = _get_generation_chain().invoke(
        {
            "question": payload.get("question", ""),
            "usable_matches": selected_matches,
            "memory_context": payload.get("memory_context"),
        }
    )
    model_latency_ms = int((perf_counter() - model_start) * 1000)
    answer = _extract_answer_payload(response)
    return {
        **payload,
        "answer": answer,
        "token_usage": _extract_token_usage(response),
        "model_latency_ms": model_latency_ms,
    }


@lru_cache(maxsize=1)
def _get_rag_pipeline_chain():
    # Full LCEL orchestration: retrieval -> context selection -> generation.
    return RunnableLambda(_run_retrieval_step) | RunnableLambda(_run_generation_step)
# Answers question from matches.
@traceable(name="rag_answer_from_matches")
def answer_question_from_matches(
    question: str,
    matches: list[dict[str, Any]],
    *,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question must not be empty.")
    normalized_matches = [_normalize_match(match, index) for index, match in enumerate(matches, start=1)]
    # take only matches that have content
    usable_matches = [match for match in normalized_matches if match["content"]]
    usable_matches = _filter_relevant_matches(cleaned_question, usable_matches)
    if not usable_matches:
        return {
            "answer": "The retrieved documents do not contain enough information to answer this confidently.",
            "sources": [],
            "documents_used": [],
            "match_count": 0,
        }
    model_start = perf_counter()
    response = _get_generation_chain().invoke(
        {
            "question": cleaned_question,
            "usable_matches": usable_matches,
            "memory_context": memory_context,
        }
    )
    model_latency_ms = int((perf_counter() - model_start) * 1000)
    answer = _extract_answer_payload(response)
    token_usage = _extract_token_usage(response)

    return {
        "answer": answer,
        "sources": _build_sources(usable_matches),
        "documents_used": _summarize_documents(usable_matches),
        "match_count": len(usable_matches),
        "model_latency_ms": model_latency_ms,
        "token_usage": token_usage,
    }
# Answers question with retrieval.
@traceable(name="rag_answer_with_retrieval")
def answer_question_with_retrieval(
    question: str,
    *,
    limit: int,
    memory_context: dict[str, Any] | None = None,
    document_ids: list[int] | None = None,
    owner_user_id: int | None = None,
) -> dict[str, Any]:
    retrieval_start = perf_counter()
    payload = _get_rag_pipeline_chain().invoke(
        {
            "question": question,
            "limit": limit,
            "memory_context": memory_context,
            "document_ids": document_ids,
            "owner_user_id": owner_user_id,
        }
    )
    retrieval_payload = payload.get("retrieval_payload", {})
    reranked_matches = payload.get("reranked_matches", [])
    selected_matches = payload.get("selected_matches", [])
    result = {
        "answer": str(payload.get("answer", "")),
        "sources": _build_sources(selected_matches),
        "documents_used": _summarize_documents(selected_matches),
        "match_count": len(selected_matches),
        "model_latency_ms": int(payload.get("model_latency_ms", 0) or 0),
        "token_usage": payload.get("token_usage") or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    retrieval_latency_ms = int((perf_counter() - retrieval_start) * 1000)
    # add extra kv pairs
    result["matches"] = selected_matches
    result["retrieved_match_count"] = len(reranked_matches)
    result["retrieval_debug"] = {
        "semantic_match_count": int(retrieval_payload.get("semantic_match_count", 0)),
        "keyword_match_count": int(retrieval_payload.get("keyword_match_count", 0)),
        "hybrid_match_count": int(retrieval_payload.get("hybrid_match_count", len(reranked_matches))),
    }
    result["retrieval_latency_ms"] = retrieval_latency_ms
    result["pipeline_trace"] = [
        "semantic_retrieval -> app.retrieval.service.search_chunk_text (LangChain Chroma)",
        "keyword_retrieval -> app.retrieval.service.keyword_search_chunk_text (LangChain BM25Retriever)",
        "hybrid_fusion -> app.retrieval.service.hybrid_search_chunk_text (LangChain EnsembleRetriever)",
        "context_select -> app.services.rag_chat._select_ranked_context",
        "answer_generation -> app.services.rag_chat._get_generation_chain (LCEL)",
        "orchestration -> app.services.rag_chat._get_rag_pipeline_chain (LCEL)",
    ]
    return result


