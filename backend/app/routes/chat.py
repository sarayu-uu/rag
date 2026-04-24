"""
File purpose:
- Exposes Phase 5 and Phase 6 chat endpoints for grounded answer generation.
- Supports both direct answer generation from supplied matches and global multi-document retrieval + generation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.mysql import MessageRole, get_db
from app.retrieval.service import ensure_vector_store_ready
from app.services.chat_history import (
    CHAT_USER_ID,
    append_chat_message,
    build_memory_context,
    get_or_create_chat_session,
    get_session_messages_payload,
    list_chat_sessions,
    serialize_session,
)
from app.services.rag_chat import answer_question_from_matches, answer_question_with_retrieval

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
def generate_answer_from_matches(payload: AnswerFromMatchesRequest) -> dict[str, Any]:
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
def chat_query(payload: ChatQueryRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        ensure_vector_store_ready()
        session, created = get_or_create_chat_session(
            db,
            question=payload.question,
            session_id=payload.session_id,
        )
        memory_context = build_memory_context(session)
        append_chat_message(
            db,
            session=session,
            role=MessageRole.USER,
            content=payload.question,
        )
        result = answer_question_with_retrieval(
            payload.question,
            limit=payload.limit,
            memory_context=memory_context,
        )
        append_chat_message(
            db,
            session=session,
            role=MessageRole.ASSISTANT,
            content=result["answer"],
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"RAG query failed: {exc}") from exc

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
def get_sessions(db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "status": "success",
        "user_id": CHAT_USER_ID,
        "sessions": list_chat_sessions(db),
    }


@router.get("/sessions/{session_id}/messages", summary="Phase 9: Get all messages for a session")
def get_session_messages(session_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = get_session_messages_payload(db, session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} was not found.")

    return {
        "status": "success",
        "user_id": CHAT_USER_ID,
        **payload,
    }
