"""
File purpose:
- Exposes a test endpoint to evaluate retrieval relevance and RAGAS metrics in one request.
- Returns score explanations so the Swagger response is self-explanatory.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.security import get_current_user, is_privileged_user
from app.models.mysql import User
from app.retrieval.embeddings import embed_query, embed_texts
from app.services.rag_chat import answer_question_with_retrieval

router = APIRouter(prefix="/test", tags=["test"])


class EvalRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question to run through retrieval + generation.")
    ground_truth: str | None = Field(
        default=None,
        description=(
            "Reference answer used by some RAGAS metrics like context recall. "
            "If omitted, those metrics are skipped."
        ),
    )
    limit: int = Field(default=5, ge=1, le=20, description="Maximum chunks used for final grounded answer.")


class RetrievalScoreItem(BaseModel):
    source_name: str = Field(..., description="Document/source filename.")
    document_id: int = Field(..., description="Internal document id.")
    chunk_index: int = Field(..., description="Chunk index inside the document.")
    retrieval_method: str = Field(..., description="How the chunk was found: semantic, keyword, or hybrid.")
    semantic_distance: float = Field(
        ...,
        description="Raw vector distance from semantic search. Lower is better.",
    )
    rerank_score: float = Field(
        ...,
        description="Hybrid score after semantic + keyword fusion. Higher is better.",
    )


class RetrievalSummary(BaseModel):
    retrieved_match_count: int = Field(..., description="Total candidates before final context selection.")
    selected_match_count: int = Field(..., description="Chunks actually used to generate the answer.")
    top_rerank_score: float = Field(..., description="Best rerank score among selected chunks.")
    avg_rerank_score: float = Field(..., description="Average rerank score among selected chunks.")
    best_semantic_distance: float = Field(..., description="Lowest semantic distance among selected chunks.")
    retrieval_latency_ms: int = Field(..., description="End-to-end retrieval latency in milliseconds.")
    retrieval_debug: dict[str, int] = Field(
        ...,
        description="Debug counts by retrieval stage (semantic, keyword, hybrid).",
    )
    sources: list[RetrievalScoreItem] = Field(..., description="Per-chunk scoring details used for inspection.")


class RagasSummary(BaseModel):
    status: str = Field(..., description="success, skipped, or failed.")
    metrics: dict[str, float] = Field(default_factory=dict, description="RAGAS metric scores.")
    skipped_metrics: list[str] = Field(
        default_factory=list,
        description="Metrics not run (for example because ground_truth was not provided).",
    )
    detail: str | None = Field(default=None, description="Extra status detail for skipped/failed runs.")


class EvalResponse(BaseModel):
    status: str = Field(..., description="Overall request status.")
    question: str = Field(..., description="Question that was evaluated.")
    answer: str = Field(..., description="Generated answer from your current RAG pipeline.")
    retrieval_summary: RetrievalSummary = Field(..., description="Retrieval and reranking quality details.")
    ragas: RagasSummary = Field(..., description="RAGAS evaluation result.")
    metric_guide: dict[str, str] = Field(
        ...,
        description="Meaning of each score so results are easy to interpret in Swagger.",
    )


class _FastEmbedLangchainEmbeddings:
    """Small adapter so RAGAS can reuse the repo's FastEmbed embeddings."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return embed_query(text)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_ragas_metrics(result: Any) -> dict[str, float]:
    if hasattr(result, "to_pandas"):
        frame = result.to_pandas()
        if not frame.empty:
            row = frame.iloc[0].to_dict()
            return {str(key): _safe_float(value) for key, value in row.items() if value is not None}
    if isinstance(result, dict):
        return {str(key): _safe_float(value) for key, value in result.items()}
    return {}


def _run_ragas(
    *,
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None,
) -> RagasSummary:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
    except Exception as exc:
        return RagasSummary(
            status="failed",
            detail=(
                "RAGAS dependencies are missing or incompatible. "
                "Install with: pip install ragas datasets"
            ),
            metrics={},
            skipped_metrics=[],
        )

    metric_objects: list[Any] = [faithfulness, answer_relevancy, context_precision]
    skipped_metrics: list[str] = []
    row: dict[str, Any] = {
        "question": question,
        "answer": answer,
        "contexts": contexts,
    }

    if ground_truth and ground_truth.strip():
        row["ground_truth"] = ground_truth.strip()
        row["reference"] = ground_truth.strip()
        try:
            from ragas.metrics import context_recall

            metric_objects.append(context_recall)
        except Exception:
            skipped_metrics.append("context_recall")
    else:
        skipped_metrics.append("context_recall (needs ground_truth)")

    try:
        from app.services.chatgroq_bot import build_chat_model

        ragas_llm = LangchainLLMWrapper(build_chat_model())
        ragas_embeddings = LangchainEmbeddingsWrapper(_FastEmbedLangchainEmbeddings())
        dataset = Dataset.from_list([row])
        result = evaluate(
            dataset=dataset,
            metrics=metric_objects,
            llm=ragas_llm,
            embeddings=ragas_embeddings,
        )
        metrics = _extract_ragas_metrics(result)
        return RagasSummary(
            status="success",
            detail=None,
            metrics=metrics,
            skipped_metrics=skipped_metrics,
        )
    except Exception as exc:
        return RagasSummary(
            status="failed",
            detail=f"RAGAS evaluation failed: {exc}",
            metrics={},
            skipped_metrics=skipped_metrics,
        )


@router.post(
    "/evaluate",
    response_model=EvalResponse,
    summary="Test: Evaluate retrieval relevance + RAGAS in one endpoint",
    description=(
        "Runs your live RAG pipeline for one question, then returns:\n"
        "1) retrieval relevance scores (semantic distance + hybrid rerank), and\n"
        "2) RAGAS quality metrics (when dependencies and model settings are available)."
    ),
)
def evaluate_rag(
    payload: EvalRequest,
    current_user: User = Depends(get_current_user),
) -> EvalResponse:
    try:
        result = answer_question_with_retrieval(
            payload.question,
            limit=payload.limit,
            owner_user_id=None if is_privileged_user(current_user) else current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Evaluation failed during retrieval/generation: {exc}") from exc

    selected_matches = result.get("matches", [])
    sources: list[RetrievalScoreItem] = [
        RetrievalScoreItem(
            source_name=str(match.get("source_name", "unknown")),
            document_id=int(match.get("document_id", 0)),
            chunk_index=int(match.get("chunk_index", 0)),
            retrieval_method=str(match.get("retrieval_method", "semantic")),
            semantic_distance=float(match.get("score", 0.0)),
            rerank_score=float(match.get("rerank_score", 0.0)),
        )
        for match in selected_matches
    ]

    rerank_scores = [item.rerank_score for item in sources]
    semantic_distances = [item.semantic_distance for item in sources]
    contexts = [str(match.get("content", "")) for match in selected_matches if str(match.get("content", "")).strip()]

    ragas_summary = _run_ragas(
        question=payload.question,
        answer=str(result.get("answer", "")),
        contexts=contexts,
        ground_truth=payload.ground_truth,
    )

    retrieval_summary = RetrievalSummary(
        retrieved_match_count=int(result.get("retrieved_match_count", len(selected_matches))),
        selected_match_count=len(selected_matches),
        top_rerank_score=max(rerank_scores) if rerank_scores else 0.0,
        avg_rerank_score=(sum(rerank_scores) / len(rerank_scores)) if rerank_scores else 0.0,
        best_semantic_distance=min(semantic_distances) if semantic_distances else 0.0,
        retrieval_latency_ms=int(result.get("retrieval_latency_ms", 0)),
        retrieval_debug={
            "semantic_match_count": int(result.get("retrieval_debug", {}).get("semantic_match_count", 0)),
            "keyword_match_count": int(result.get("retrieval_debug", {}).get("keyword_match_count", 0)),
            "hybrid_match_count": int(result.get("retrieval_debug", {}).get("hybrid_match_count", 0)),
        },
        sources=sources,
    )

    return EvalResponse(
        status="success",
        question=payload.question,
        answer=str(result.get("answer", "")),
        retrieval_summary=retrieval_summary,
        ragas=ragas_summary,
        metric_guide={
            "semantic_distance": "Raw vector distance from semantic retrieval. Lower is better.",
            "rerank_score": "Final hybrid relevance score after semantic + keyword fusion. Higher is better.",
            "top_rerank_score": "Best retrieved chunk quality for this query.",
            "avg_rerank_score": "Overall average relevance across used chunks.",
            "faithfulness": "How well the answer is grounded in the provided contexts.",
            "answer_relevancy": "How directly the answer addresses the question.",
            "context_precision": "How much of retrieved context is relevant to the answer.",
            "context_recall": "How well retrieved context covers the reference/ground-truth answer.",
        },
    )
