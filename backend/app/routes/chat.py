"""
File purpose:
- Exposes Phase 5 and Phase 6 chat endpoints for grounded answer generation.
- Supports both direct answer generation from supplied matches and global multi-document retrieval + generation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.permissions import build_retrieval_scope_with_fallback
from app.auth.security import get_current_user
from app.models.mysql import ChatMessage, ChatSession, MessageRole, MetricUsage, User, get_db
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
from app.telemetry.service import estimate_cost

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
    document_ids: list[int] | None = Field(
        default=None,
        description="Optional explicit document ids to constrain retrieval.",
    )
    session_id: int | None = Field(
        default=None,
        ge=1,
        description="Existing chat session id. Omit this to start a new session.",
    )


#not used for development
@router.post(
    "/answer-from-matches",
    summary="Phase 5: Generate a grounded answer from provided matches",
    description=(
        "Usage: Primarily for testing/manual experiments. "
        "Purpose: generate an answer from caller-supplied retrieval matches without running retrieval."
    ),
)
# Builds an answer from already retrieved matches.
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


# this is being used 
@router.post(
    "/query",
    summary="Phase 6: Search across all indexed documents and generate a grounded answer",
    description=(
        "Usage: Main frontend chat endpoint. "
        "Purpose: retrieve relevant chunks, generate grounded answer, and persist chat history."
    ),
)
# Processes the main chat question request.
def chat_query(
    payload: ChatQueryRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        #check if vector db is ready
        ensure_vector_store_ready()
        # check what documents is allowed and take only those
        retrieval_scope = build_retrieval_scope_with_fallback(
            db,
            current_user,
            permission_field="can_query",
            fallback_permission_field="can_read",
        )
        scoped_document_ids = retrieval_scope.document_ids
        if payload.document_ids is not None:
            requested_ids = [int(document_id) for document_id in payload.document_ids]
            allowed_set = set(scoped_document_ids)
            disallowed_ids = [document_id for document_id in requested_ids if document_id not in allowed_set]
            if disallowed_ids:
                raise HTTPException(
                    status_code=403,
                    detail=f"You do not have query access to document ids: {sorted(set(disallowed_ids))}.",
                )
            scoped_document_ids = requested_ids

        if not scoped_document_ids:
            raise HTTPException(status_code=400, detail="No accessible documents selected for retrieval.")

        # this loads the session or creates a new one
        session, created = get_or_create_chat_session(
            db,
            question=payload.question,
            session_id=payload.session_id,
            user_id=current_user.id,
        )
        if is_session_at_limit(session):
            raise HTTPException(status_code=403, detail="100% chat used. Start a new chat to continue.")
        # builds the context of recent messages
        memory_context = build_memory_context(session)
        question_for_usage = payload.question.strip()
        #uploads the qustion to the chat message as a user question
        user_message = append_chat_message(
            db,
            session=session,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=question_for_usage,
            token_count=0,
        )
        #here the retvival process happens
        result = answer_question_with_retrieval(
            question_for_usage,
            limit=payload.limit,
            memory_context=memory_context,
            document_ids=scoped_document_ids,
            owner_user_id=retrieval_scope.owner_user_id,
        )
        token_usage = result.get("token_usage") or {}
        model_token_input = int(token_usage.get("input_tokens", 0) or 0)
        model_token_output = int(token_usage.get("output_tokens", 0) or 0)
        model_token_total = int(token_usage.get("total_tokens", model_token_input + model_token_output) or 0)

        user_message_tokens = model_token_input
        assistant_message_tokens = model_token_output

        user_message.token_count = user_message_tokens
        db.flush()
        append_chat_message(
            db,
            session=session,
            user_id=current_user.id,
            role=MessageRole.ASSISTANT,
            content=result["answer"],
            token_count=assistant_message_tokens,
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
        if exc.__class__.__name__ == "APIConnectionError":
            raise HTTPException(
                status_code=503,
                detail=(
                    "LLM provider connection failed. The server could not reach the model API. "
                    "Check internet/firewall/proxy settings and verify outbound HTTPS access."
                ),
            ) from exc
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


@router.get(
    "/sessions",
    summary="Phase 9: List persistent chat sessions",
    description="Usage: Used by frontend chat sidebar. Purpose: lists the current user's saved chat sessions.",
)
# Gets sessions.
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "status": "success",
        "user_id": current_user.id,
        "sessions": list_chat_sessions(db, user_id=current_user.id),
    }


# get chat history
@router.get(
    "/sessions/{session_id}/messages",
    summary="Phase 9: Get all messages for a session",
    description="Usage: Used by frontend transcript view. Purpose: returns all messages for one user-owned session.",
)
# Gets session messages.
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

# delete a chat
@router.delete(
    "/sessions/{session_id}",
    summary="Phase 9: Delete a chat session",
    description="Usage: Used by frontend chat sidebar actions. Purpose: deletes one user-owned chat session.",
)
# Deletes session.
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} was not found.")

    try:
        # Explicitly delete dependent rows to support existing DBs
        # where FK constraints may not be ON DELETE CASCADE.
        db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        # Preserve historical token usage while allowing session deletion
        # by detaching metrics from the deleted session.
        db.execute(
            update(MetricUsage)
            .where(MetricUsage.session_id == session_id)
            .values(session_id=None)
        )
        db.delete(session)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete chat session from MySQL: {exc}") from exc

    return {
        "status": "success",
        "message": "Chat session deleted successfully.",
        "session_id": session_id,
    }


