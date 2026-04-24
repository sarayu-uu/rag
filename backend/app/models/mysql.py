"""
File purpose:
- SQLAlchemy MySQL database setup and core ORM models for the RAG app.
- Defines engine/session/base and all tables from the Phase 1 data model.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    inspect,
    select,
    String,
    text,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.config.settings import (
    DATABASE_URL,
    DEFAULT_INGESTION_EMAIL,
    DEFAULT_INGESTION_PASSWORD_HASH,
    DEFAULT_INGESTION_USERNAME,
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class RoleName(str, PyEnum):
    ADMIN = "Admin"
    MANAGER = "Manager"
    ANALYST = "Analyst"
    VIEWER = "Viewer"
    GUEST = "Guest"


ROLE_DESCRIPTIONS: dict[RoleName, str] = {
    RoleName.ADMIN: "Full administrative access across the platform.",
    RoleName.MANAGER: "Can manage team documents, users, and access rules.",
    RoleName.ANALYST: "Can ingest documents and run retrieval workflows.",
    RoleName.VIEWER: "Can view approved content and grounded answers.",
    RoleName.GUEST: "Limited read-only access to explicitly shared resources.",
}


class DocumentStatus(str, PyEnum):
    UPLOADED = "uploaded"
    PROCESSED = "processed"
    FAILED = "failed"


class SessionStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    CLOSED_LIMIT = "CLOSED_LIMIT"
    CLOSED_MANUAL = "CLOSED_MANUAL"


class MessageRole(str, PyEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class RequestType(str, PyEnum):
    INGESTION = "ingestion"
    RETRIEVAL = "retrieval"
    CHAT = "chat"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[RoleName] = mapped_column(Enum(RoleName), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email LIKE '%@gmail.com'", name="ck_users_email_gmail"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    role: Mapped["Role"] = relationship(back_populates="users")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="uploader",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Permission.user_id",
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    upload_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus),
        default=DocumentStatus.UPLOADED,
        nullable=False,
    )
    uploader: Mapped["User"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    permissions_tags: Mapped[str] = mapped_column(String(2000), nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    document: Mapped["Document"] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tokens_used_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped["User"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    metrics: Mapped[list["MetricUsage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True, index=True)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_query: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    document: Mapped["Document"] = relationship(back_populates="permissions")
    user: Mapped["User"] = relationship(
        back_populates="permissions",
        foreign_keys=[user_id],
    )


class MetricUsage(Base):
    __tablename__ = "metrics_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    request_type: Mapped[RequestType] = mapped_column(Enum(RequestType), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    token_input: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_output: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ingestion_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieval_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    session: Mapped["ChatSession"] = relationship(back_populates="metrics")


def init_db() -> None:
    """Create all tables and seed baseline reference data."""
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    seed_roles()


def ensure_schema_updates() -> None:
    """Apply lightweight schema updates for existing local databases."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "document_chunks" not in table_names:
        return

    chunk_columns = {column["name"] for column in inspector.get_columns("document_chunks")}
    with engine.begin() as connection:
        if "permissions_tags" not in chunk_columns:
            connection.execute(
                text(
                    "ALTER TABLE document_chunks "
                    "ADD COLUMN permissions_tags VARCHAR(2000) NOT NULL DEFAULT '[]'"
                )
            )


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> None:
    """Raise if the configured database is unreachable."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def seed_roles() -> None:
    """Ensure the baseline RBAC roles exist for future phases."""
    with SessionLocal() as db:
        existing_roles = set(db.scalars(select(Role.name)).all())
        missing_roles = [
            Role(name=role_name, description=ROLE_DESCRIPTIONS[role_name])
            for role_name in RoleName
            if role_name not in existing_roles
        ]

        if not missing_roles:
            return

        db.add_all(missing_roles)
        db.commit()


def get_or_create_default_ingestion_user(db: Session) -> User:
    """Return a fallback uploader user for ingestion flows before auth exists."""
    user = db.scalar(select(User).where(User.email == DEFAULT_INGESTION_EMAIL))
    if user is not None:
        return user

    analyst_role = db.scalar(select(Role).where(Role.name == RoleName.ANALYST))
    if analyst_role is None:
        analyst_role = Role(name=RoleName.ANALYST, description=ROLE_DESCRIPTIONS[RoleName.ANALYST])
        db.add(analyst_role)
        db.flush()

    user = User(
        username=DEFAULT_INGESTION_USERNAME,
        email=DEFAULT_INGESTION_EMAIL,
        password_hash=DEFAULT_INGESTION_PASSWORD_HASH,
        role_id=analyst_role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user
