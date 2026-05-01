"""
File purpose:
- Exposes Phase 5 and Phase 6 chat endpoints for grounded answer generation.
- Supports both direct answer generation from supplied matches and global multi-document retrieval + generation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.permissions import accessible_document_ids
from app.auth.security import get_current_user
from app.models.mysql import ChatSession, MessageRole, User, get_db
from app.retrieval.service import ensure_vector_store_ready
from app.services.chat_history import (
    append_chat_message,
    build_memory_context,
    get_or_create_chat_session,
    get_session_messages_payload,
    is_session_at_limit,
    list_chat_sessions,
    serialize_session,
)
from app.services.rag_chat import answer_question_from_matches, answer_question_with_retrieval
from app.telemetry.service import estimate_cost, estimate_token_count

router = APIRouter(prefix="/chat", tags=["chat"])


class RetrievedMatch(BaseModel):
    id: str | None = None
    score: float = Field(default=0.0)
    document_id: int = Field(..., gt=0)
    chunk_index: int = Field(..., ge=0)
    page_number: int | None = None
    source_name: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class AnswerFromMatchesRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question to answer from the provided matches.")
    matches: list[RetrievedMatch] = Field(
        default_factory=list,
        description="Retrieved chunks that should be given to the LLM as grounding context.",
    )


class ChatQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question to answer from indexed documents.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of chunks to retrieve before generation.")
    session_id: int | None = Field(
        default=None,
        ge=1,
        description="Existing chat session id. Omit this to start a new session.",
    )


@router.post("/answer-from-matches", summary="Phase 5: Generate a grounded answer from provided matches")
def generate_answer_from_matches(
    payload: AnswerFromMatchesRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        result = answer_question_from_matches(
            payload.question,
            [match.model_dump() for match in payload.matches],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM answer generation failed: {exc}") from exc

    return {
        "status": "success",
        "question": payload.question,
        **result,
    }


@router.post("/query", summary="Phase 6: Search across all indexed documents and generate a grounded answer")
def chat_query(
    payload: ChatQueryRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        ensure_vector_store_ready()
        session, created = get_or_create_chat_session(
            db,
            question=payload.question,
            session_id=payload.session_id,
            user_id=current_user.id,
        )
        if is_session_at_limit(session):
            raise HTTPException(status_code=403, detail="100% chat used. Start a new chat to continue.")
        memory_context = build_memory_context(session)
        question_for_usage = payload.question.strip()
        user_message = append_chat_message(
            db,
            session=session,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=question_for_usage,
            token_count=0,
        )
        result = answer_question_with_retrieval(
            question_for_usage,
            limit=payload.limit,
            memory_context=memory_context,
            document_ids=accessible_document_ids(db, current_user, permission_field="can_query"),
        )
        token_usage = result.get("token_usage") or {}
        model_token_input = int(token_usage.get("input_tokens", 0) or 0)
        model_token_output = int(token_usage.get("output_tokens", 0) or 0)
        model_token_total = int(token_usage.get("total_tokens", model_token_input + model_token_output) or 0)

        if model_token_total <= 0:
            model_token_input = estimate_token_count(question_for_usage)
            model_token_output = estimate_token_count(result.get("answer", ""))
            model_token_total = model_token_input + model_token_output

        visible_question_tokens = estimate_token_count(question_for_usage)
        visible_answer_tokens = estimate_token_count(result.get("answer", ""))

        user_message.token_count = visible_question_tokens
        db.flush()
        append_chat_message(
            db,
            session=session,
            user_id=current_user.id,
            role=MessageRole.ASSISTANT,
            content=result["answer"],
            token_count=visible_answer_tokens,
        )
        db.commit()
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"RAG query failed: {exc}") from exc

    estimated_cost = estimate_cost(model_token_input, model_token_output)

    response.headers["X-Telemetry-Session-Id"] = str(session.id)
    response.headers["X-Telemetry-Token-Input"] = str(model_token_input)
    response.headers["X-Telemetry-Token-Output"] = str(model_token_output)
    response.headers["X-Telemetry-Token-Total"] = str(model_token_total)
    response.headers["X-Telemetry-Estimated-Cost"] = str(estimated_cost)
    response.headers["X-Telemetry-Retrieval-Latency-Ms"] = str(result.get("retrieval_latency_ms", 0))
    response.headers["X-Telemetry-Model-Latency-Ms"] = str(result.get("model_latency_ms", 0))

    return {
        "status": "success",
        "question": payload.question,
        "session": {
            **serialize_session(session),
            "created": created,
        },
        **result,
    }


@router.get("/sessions", summary="Phase 9: List persistent chat sessions")
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "status": "success",
        "user_id": current_user.id,
        "sessions": list_chat_sessions(db, user_id=current_user.id),
    }


@router.get("/sessions/{session_id}/messages", summary="Phase 9: Get all messages for a session")
def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    payload = get_session_messages_payload(db, session_id, user_id=current_user.id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} was not found.")

    return {
        "status": "success",
        "user_id": current_user.id,
        **payload,
    }


@router.delete("/sessions/{session_id}", summary="Phase 9: Delete a chat session")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} was not found.")

    db.delete(session)
    db.commit()

    return {
        "status": "success",
        "message": "Chat session deleted successfully.",
        "session_id": session_id,
    }
