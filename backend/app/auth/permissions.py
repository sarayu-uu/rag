"""
File purpose:
- Centralizes document permission checks for owner, role, and user grants.
- Keeps document listing, retrieval, and chat authorization consistent.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models.mysql import Document, Permission, Role, RoleName, User


@dataclass(frozen=True)
class RetrievalScope:
    """Normalized retrieval authorization scope for one user request."""

    document_ids: list[int]
    owner_user_id: int | None = None
# Checks whether the user can access all documents.
def _has_global_document_access(user: User, *, permission_field: str) -> bool:
    role_name = user.role.name if user.role else None
    if role_name == RoleName.ADMIN:
        return True
    return False


def _explicit_permission_exists_clause(user: User, *, permission_field: str):
    permission_column = getattr(Permission, permission_field)
    return exists(
        select(Permission.id).where(
            Permission.document_id == Document.id,
            permission_column.is_(True),
            or_(
                Permission.user_id == user.id,
                Permission.role_id == user.role_id,
            ),
        )
    )
# Builds the document access filter for queries.
def document_access_filter(user: User, *, permission_field: str):
    if _has_global_document_access(user, permission_field=permission_field):
        return None

    role_name = user.role.name if user.role else None
    explicit_access = _explicit_permission_exists_clause(user, permission_field=permission_field)

    if role_name == RoleName.MANAGER:
        # Manager default visibility:
        # - own docs
        # - docs uploaded by analysts in manager's team
        # - any explicitly granted docs
        team_analyst_uploader_exists = exists(
            select(User.id).where(
                User.id == Document.upload_user_id,
                User.manager_user_id == user.id,
                User.role.has(Role.name == RoleName.ANALYST),
            )
        )
        return or_(
            Document.upload_user_id == user.id,
            team_analyst_uploader_exists,
            explicit_access,
        )

    if role_name == RoleName.ANALYST:
        # Analyst default visibility:
        # - own docs
        # - docs uploaded by their manager
        # - explicit grants
        manager_uploader_match = exists(
            select(User.id).where(
                User.id == Document.upload_user_id,
                User.id == user.manager_user_id,
            )
        )
        return or_(
            Document.upload_user_id == user.id,
            manager_uploader_match,
            explicit_access,
        )

    # Viewer default visibility: explicit grants only.
    return explicit_access
# Returns the document ids the user can access.
def accessible_document_ids(db: Session, user: User, *, permission_field: str) -> list[int] | None:
    if _has_global_document_access(user, permission_field=permission_field):
        return None

    access_filter = document_access_filter(user, permission_field=permission_field)
    if access_filter is None:
        return None

    return list(db.scalars(select(Document.id).where(access_filter)).all())


def build_retrieval_scope(db: Session, user: User, *, permission_field: str) -> RetrievalScope:
    """
    Build one canonical retrieval scope from RBAC rules.

    - Admin/Manager-like users get all existing document ids.
    - Other users get only explicitly accessible ids.
    """
    allowed_document_ids = accessible_document_ids(db, user, permission_field=permission_field)
    if allowed_document_ids is None:
        allowed_document_ids = list(db.scalars(select(Document.id)).all())

    return RetrievalScope(
        document_ids=[int(document_id) for document_id in allowed_document_ids],
        owner_user_id=None,
    )


def build_retrieval_scope_with_fallback(
    db: Session,
    user: User,
    *,
    permission_field: str,
    fallback_permission_field: str | None = None,
) -> RetrievalScope:
    """
    Build retrieval scope and optionally fall back to another permission field
    when the primary scope resolves to no documents.
    """
    primary_scope = build_retrieval_scope(db, user, permission_field=permission_field)
    if primary_scope.document_ids or not fallback_permission_field:
        return primary_scope

    fallback_scope = build_retrieval_scope(db, user, permission_field=fallback_permission_field)
    return fallback_scope


