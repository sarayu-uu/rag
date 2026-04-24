"""
File purpose:
- Implements Phase 9 chat persistence for sessions, messages, and lightweight prompt memory.
- Keeps `user_id = 1` as the temporary authenticated user until auth is added.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.mysql import ChatMessage, ChatSession, MessageRole, Role, RoleName, SessionStatus, User

CHAT_USER_ID = 1
CHAT_TOKEN_LIMIT = 10000
DEFAULT_MESSAGE_TOKEN_COUNT = 100
CHAT_USERNAME = "chat_user_1"
CHAT_EMAIL = "chat.user.1@gmail.com"
CHAT_PASSWORD_HASH = "auth-not-enabled"
RECENT_MESSAGE_LIMIT = 6
OLDER_SUMMARY_LIMIT = 1200
SESSION_TITLE_WORDS = 3


def first_words(text: str, count: int = SESSION_TITLE_WORDS) -> str:
    return " ".join(text.strip().split()[:count])


def ensure_chat_user(db: Session) -> User:
    user = db.get(User, CHAT_USER_ID)
    if user is not None:
        return user

    analyst_role = db.scalar(select(Role).where(Role.name == RoleName.ANALYST))
    if analyst_role is None:
        analyst_role = Role(name=RoleName.ANALYST, description="Temporary role for chat user 1.")
        db.add(analyst_role)
        db.flush()

    user = User(
        id=CHAT_USER_ID,
        username=CHAT_USERNAME,
        email=CHAT_EMAIL,
        password_hash=CHAT_PASSWORD_HASH,
        role_id=analyst_role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def create_chat_session(db: Session, *, question: str) -> ChatSession:
    ensure_chat_user(db)
    session = ChatSession(
        user_id=CHAT_USER_ID,
        title=first_words(question),
        tokens_used_total=0,
        token_limit=CHAT_TOKEN_LIMIT,
        status=SessionStatus.ACTIVE,
        started_at=datetime.utcnow(),
        ended_at=None,
    )
    db.add(session)
    db.flush()
    return session


def get_chat_session(db: Session, session_id: int) -> ChatSession | None:
    return db.scalar(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id, ChatSession.user_id == CHAT_USER_ID)
    )


def get_or_create_chat_session(db: Session, *, question: str, session_id: int | None) -> tuple[ChatSession, bool]:
    if session_id is None:
        return create_chat_session(db, question=question), True

    session = get_chat_session(db, session_id)
    if session is None:
        return create_chat_session(db, question=question), True

    if not session.title:
        session.title = first_words(question)
    session.token_limit = CHAT_TOKEN_LIMIT
    session.status = SessionStatus.ACTIVE
    session.ended_at = None
    db.flush()
    return session, False


def append_chat_message(
    db: Session,
    *,
    session: ChatSession,
    role: MessageRole,
    content: str,
    token_count: int = DEFAULT_MESSAGE_TOKEN_COUNT,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        user_id=CHAT_USER_ID,
        role=role,
        content=content.strip(),
        token_count=token_count,
        created_at=datetime.utcnow(),
    )
    db.add(message)
    db.flush()
    refresh_session_totals(db, session)
    return message


def refresh_session_totals(db: Session, session: ChatSession) -> None:
    session.tokens_used_total = int(
        db.scalar(
            select(func.coalesce(func.sum(ChatMessage.token_count), 0)).where(
                ChatMessage.session_id == session.id
            )
        )
        or 0
    )
    session.token_limit = CHAT_TOKEN_LIMIT
    session.status = SessionStatus.ACTIVE
    session.ended_at = None
    db.flush()


def build_memory_context(session: ChatSession) -> dict[str, Any]:
    messages = sorted(session.messages, key=lambda item: (item.created_at, item.id))
    recent_messages = messages[-RECENT_MESSAGE_LIMIT:]
    older_messages = messages[:-RECENT_MESSAGE_LIMIT]

    summary_lines: list[str] = []
    current_chars = 0
    for message in older_messages:
        line = f"{message.role.value}: {' '.join(message.content.split())}"
        if current_chars + len(line) + 1 > OLDER_SUMMARY_LIMIT:
            break
        summary_lines.append(line)
        current_chars += len(line) + 1

    return {
        "recent_messages": [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in recent_messages
        ],
        "older_summary": "\n".join(summary_lines),
        "message_count": len(messages),
    }


def serialize_session(session: ChatSession) -> dict[str, Any]:
    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "title": session.title,
        "tokens_used_total": session.tokens_used_total,
        "token_limit": session.token_limit,
        "status": session.status.value,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


def list_chat_sessions(db: Session) -> list[dict[str, Any]]:
    sessions = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == CHAT_USER_ID)
        .order_by(ChatSession.started_at.desc(), ChatSession.id.desc())
    ).all()
    return [serialize_session(session) for session in sessions]


def get_session_messages_payload(db: Session, session_id: int) -> dict[str, Any] | None:
    session = get_chat_session(db, session_id)
    if session is None:
        return None

    ordered_messages = sorted(session.messages, key=lambda item: (item.created_at, item.id))
    return {
        **serialize_session(session),
        "messages": [
            {
                "id": message.id,
                "session_id": message.session_id,
                "user_id": message.user_id,
                "role": message.role.value,
                "content": message.content,
                "token_count": message.token_count,
                "created_at": message.created_at.isoformat(),
            }
            for message in ordered_messages
        ],
    }
