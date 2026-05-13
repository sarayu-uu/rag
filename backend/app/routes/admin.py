"""
File purpose:
- Exposes lightweight admin and RBAC endpoints for users and document permissions.
- Applies role checks using the current JWT-authenticated user.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.auth.security import get_current_user
from app.models.mysql import (
    ChatMessage,
    ChatSession,
    Document,
    DocumentChunk,
    MetricUsage,
    Permission,
    Role,
    RoleName,
    User,
    get_db,
)
from app.telemetry.service import estimate_cost

router = APIRouter(prefix="/admin", tags=["admin"])


class UpdateUserRoleRequest(BaseModel):
    role: RoleName
    manager_user_id: int | None = Field(default=None, gt=0)


class UpdateDocumentPermissionRequest(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    role_id: int | None = Field(default=None, gt=0)
    role: RoleName | None = None
    all_team_analysts: bool = False
    can_read: bool = False
    can_query: bool = False
    can_edit: bool = False
# Ensures the current user is an admin.
def _require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    role_name = current_user.role.name if current_user.role else None
    if role_name not in {RoleName.ADMIN, RoleName.MANAGER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager role required.",
        )
    return current_user
# Ensures the current user can manage other users.
def _require_supervising_admin(current_user: User = Depends(get_current_user)) -> User:
    role_name = current_user.role.name if current_user.role else None
    if role_name != RoleName.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return current_user
# Converts user into a response-friendly format.
def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.name.value if user.role else None,
        "manager_user_id": user.manager_user_id,
        "manager_username": user.manager.username if getattr(user, "manager", None) else None,
        "is_active": user.is_active,
        "is_deleted": user.is_deleted,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }
# Converts permission into a response-friendly format.
def _serialize_permission(permission: Permission) -> dict[str, Any]:
    return {
        "id": permission.id,
        "document_id": permission.document_id,
        "user_id": permission.user_id,
        "role_id": permission.role_id,
        "role": permission.role.name.value if getattr(permission, "role", None) else None,
        "can_read": permission.can_read,
        "can_query": permission.can_query,
        "can_edit": permission.can_edit,
        "granted_by": permission.granted_by,
        "granted_at": permission.granted_at.isoformat(),
    }


def _require_usage_admin(current_user: User = Depends(get_current_user)) -> User:
    role_name = current_user.role.name if current_user.role else None
    if role_name != RoleName.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return current_user


@router.get(
    "/users",
    summary="Phase 12: List users for admin workflows",
    description="Usage: Used by frontend admin users page. Purpose: list users for privileged role management.",
)
# Lists users.
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin_user),
) -> dict[str, Any]:
    statement = (
        select(User)
        .options(joinedload(User.role), joinedload(User.manager))
        .order_by(User.created_at.desc(), User.id.desc())
    )
    role_name = current_user.role.name if current_user.role else None
    if role_name == RoleName.MANAGER:
        statement = statement.where(
            or_(
                User.id == current_user.id,
                User.manager_user_id == current_user.id,
                User.role.has(Role.name == RoleName.VIEWER),
            )
        )

    users = db.scalars(statement).unique().all()
    return {
        "status": "success",
        "count": len(users),
        "users": [_serialize_user(user) for user in users],
    }


@router.patch(
    "/users/{user_id}/role",
    summary="Phase 12: Update a user's RBAC role",
    description="Usage: Used by frontend admin users page. Purpose: update a user's assigned RBAC role.",
)
# Updates user role.
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin_user),
) -> dict[str, Any]:
    user = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.manager))
        .where(User.id == user_id)
    )
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} was not found.")

    role = db.scalar(select(Role).where(Role.name == payload.role))
    if role is None:
        raise HTTPException(status_code=404, detail=f"Role {payload.role.value} was not found.")

    actor_role = current_user.role.name if current_user.role else None
    target_current_role = user.role.name if user.role else None

    if actor_role == RoleName.MANAGER:
        allowed = {
            (RoleName.VIEWER, RoleName.ANALYST),
            (RoleName.ANALYST, RoleName.VIEWER),
        }
        if (target_current_role, payload.role) not in allowed:
            raise HTTPException(
                status_code=403,
                detail="Managers can only change Viewer<->Analyst roles.",
            )
        if payload.role == RoleName.ANALYST:
            # Manager promotion keeps analyst in same manager team.
            payload.manager_user_id = current_user.id
        if target_current_role == RoleName.ANALYST and user.manager_user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Managers can only update analysts in their own team.",
            )
        if payload.manager_user_id not in {None, current_user.id}:
            raise HTTPException(
                status_code=403,
                detail="Managers cannot assign analysts to another manager.",
            )

    if actor_role == RoleName.ADMIN and payload.role == RoleName.ANALYST and payload.manager_user_id is None:
        raise HTTPException(
            status_code=400,
            detail="manager_user_id is required when assigning Analyst role.",
        )

    manager_user_id = payload.manager_user_id
    if payload.role == RoleName.ANALYST:
        manager = db.scalar(select(User).options(joinedload(User.role)).where(User.id == manager_user_id))
        if manager is None:
            raise HTTPException(status_code=404, detail=f"Manager user {manager_user_id} was not found.")
        manager_role = manager.role.name if manager.role else None
        if manager_role != RoleName.MANAGER:
            raise HTTPException(status_code=400, detail="Assigned manager_user_id must reference a Manager user.")
    else:
        manager_user_id = None

    user.role_id = role.id
    user.manager_user_id = manager_user_id
    db.commit()
    user = db.scalar(
        select(User)
        .options(joinedload(User.role), joinedload(User.manager))
        .where(User.id == user_id)
    ) or user

    return {
        "status": "success",
        "message": "User role updated successfully.",
        "user": _serialize_user(user),
    }


@router.delete(
    "/users/{user_id}",
    summary="Phase 12: Soft-delete a non-admin user",
    description="Usage: Used by frontend admin users page. Purpose: mark a non-admin user as deleted while retaining historical data.",
)
# Deletes user.
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_supervising_admin),
) -> dict[str, Any]:
    user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} was not found.")

    user_role = user.role.name if user.role else None
    if user_role == RoleName.ADMIN:
        raise HTTPException(status_code=403, detail="Admin users cannot be deleted.")

    if user.id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot delete your own account.")

    if user.is_deleted:
        raise HTTPException(status_code=400, detail="User is already deleted.")

    serialized_user = _serialize_user(user)
    try:
        # Soft-delete only. Keep chats/documents/metrics for audit and historical reporting.
        user.is_deleted = True
        user.is_active = False
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to soft-delete user in MySQL: {exc}") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Failed to soft-delete user: {exc}") from exc

    return {
        "status": "success",
        "message": "User soft-deleted successfully.",
        "user": serialized_user,
    }


@router.patch(
    "/documents/{document_id}/permissions",
    summary="Phase 12: Update one document permission rule",
    description="Usage: Used by frontend admin permissions page. Purpose: set or update document-level read/query/edit rules.",
)
# Updates document permissions.
def update_document_permissions(
    document_id: int,
    payload: UpdateDocumentPermissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin_user),
) -> dict[str, Any]:
    if payload.role is not None and payload.role_id is not None:
        raise HTTPException(status_code=400, detail="Provide either role or role_id, not both.")

    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} was not found.")

    target_user = None
    if payload.user_id is not None:
        target_user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == payload.user_id))
    if payload.user_id is not None and target_user is None:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} was not found.")
    if target_user is not None and target_user.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot grant permissions to a deleted user.")

    role_id = payload.role_id
    if payload.role is not None:
        role = db.scalar(select(Role).where(Role.name == payload.role))
        if role is None:
            raise HTTPException(status_code=404, detail=f"Role {payload.role.value} was not found.")
        role_id = role.id
    elif role_id is not None and db.get(Role, role_id) is None:
        raise HTTPException(status_code=404, detail=f"Role {role_id} was not found.")

    if payload.user_id is None and role_id is None and not payload.all_team_analysts:
        raise HTTPException(status_code=400, detail="Provide either user_id or role for the permission rule.")

    actor_role = current_user.role.name if current_user.role else None
    if payload.all_team_analysts and actor_role != RoleName.MANAGER:
        raise HTTPException(status_code=403, detail="all_team_analysts option is only available for managers.")
    if payload.all_team_analysts and (payload.user_id is not None or role_id is not None):
        raise HTTPException(
            status_code=400,
            detail="When all_team_analysts is true, do not pass user_id/role/role_id.",
        )

    if actor_role == RoleName.MANAGER:
        # Managers can manage permissions on:
        # - docs they uploaded, or
        # - docs where they have explicit can_edit access (user- or role-level grant).
        if document.upload_user_id != current_user.id:
            manager_can_delegate = db.scalar(
                select(Permission.id).where(
                    Permission.document_id == document_id,
                    Permission.can_edit.is_(True),
                    or_(
                        Permission.user_id == current_user.id,
                        Permission.role_id == current_user.role_id,
                    ),
                )
            )
            if manager_can_delegate is None:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Managers can only modify permissions for their own uploaded documents "
                        "or documents where they have can_edit access."
                    ),
                )
        # Managers can only grant user-specific access to their own analysts.
        if payload.user_id is not None:
            target_role = target_user.role.name if target_user and target_user.role else None
            if target_role != RoleName.ANALYST or target_user.manager_user_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Managers can grant access only to analysts in their own team.",
                )
        # Managers should not grant role-wide rules.
        if role_id is not None:
            raise HTTPException(status_code=403, detail="Managers cannot grant role-wide document permissions.")

    if payload.all_team_analysts:
        analyst_users = db.scalars(
            select(User)
            .options(joinedload(User.role))
            .where(
                User.manager_user_id == current_user.id,
                User.role.has(Role.name == RoleName.ANALYST),
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        ).all()
        updated_permissions: list[Permission] = []
        for analyst in analyst_users:
            permission = db.scalar(
                select(Permission).where(
                    Permission.document_id == document_id,
                    Permission.user_id == analyst.id,
                    Permission.role_id.is_(None),
                )
            )
            if permission is None:
                permission = Permission(
                    document_id=document_id,
                    user_id=analyst.id,
                    role_id=None,
                    granted_by=current_user.id,
                )
                db.add(permission)
            permission.can_read = payload.can_read
            permission.can_query = payload.can_query
            permission.can_edit = payload.can_edit
            permission.granted_by = current_user.id
            updated_permissions.append(permission)

        db.commit()
        for permission in updated_permissions:
            db.refresh(permission)

        return {
            "status": "success",
            "message": "Document permissions updated successfully for all analysts in manager team.",
            "count": len(updated_permissions),
            "permissions": [_serialize_permission(permission) for permission in updated_permissions],
        }

    permission = db.scalar(
        select(Permission).where(
            Permission.document_id == document_id,
            Permission.user_id == payload.user_id,
            Permission.role_id == role_id,
        )
    )

    if permission is None:
        permission = Permission(
            document_id=document_id,
            user_id=payload.user_id,
            role_id=role_id,
            granted_by=current_user.id,
        )
        db.add(permission)

    permission.can_read = payload.can_read
    permission.can_query = payload.can_query
    permission.can_edit = payload.can_edit
    permission.granted_by = current_user.id
    db.commit()
    db.refresh(permission)

    return {
        "status": "success",
        "message": "Document permissions updated successfully.",
        "permission": _serialize_permission(permission),
    }


@router.get(
    "/users/{user_id}/usage",
    summary="Admin users insights for admin",
    description="Usage: Used by admin-only users page action. Purpose: show token spend, documents, and chats for one user.",
)
def get_user_usage_details(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_usage_admin),
) -> dict[str, Any]:
    user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} was not found.")

    total_tokens_spent = int(
        db.scalar(
            select(func.coalesce(func.sum(MetricUsage.token_total), 0)).where(MetricUsage.user_id == user_id)
        )
        or 0
    )
    total_token_input = int(
        db.scalar(
            select(func.coalesce(func.sum(MetricUsage.token_input), 0)).where(MetricUsage.user_id == user_id)
        )
        or 0
    )
    total_token_output = int(
        db.scalar(
            select(func.coalesce(func.sum(MetricUsage.token_output), 0)).where(MetricUsage.user_id == user_id)
        )
        or 0
    )
    total_estimated_cost = float(estimate_cost(total_token_input, total_token_output))

    documents = db.scalars(
        select(Document)
        .where(Document.upload_user_id == user_id)
        .order_by(Document.uploaded_at.desc(), Document.id.desc())
    ).all()

    sessions = db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.started_at.desc(), ChatSession.id.desc())
    ).all()

    session_ids = [session.id for session in sessions]
    session_messages_map: dict[int, list[ChatMessage]] = {session_id: [] for session_id in session_ids}
    if session_ids:
        messages = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id.in_(session_ids))
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        ).all()
        for message in messages:
            session_messages_map.setdefault(message.session_id, []).append(message)

    return {
        "status": "success",
        "user": _serialize_user(user),
        "total_tokens_spent": total_tokens_spent,
        "total_estimated_cost_usd": round(total_estimated_cost, 6),
        "documents": [
            {
                "id": document.id,
                "title": document.title,
                "file_type": document.file_type,
                "status": document.status.value if document.status else None,
                "uploaded_at": document.uploaded_at.isoformat(),
            }
            for document in documents
        ],
        "chats": [
            {
                "session_id": session.id,
                "title": session.title,
                "status": session.status.value if session.status else None,
                "tokens_used_total": session.tokens_used_total,
                "started_at": session.started_at.isoformat(),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "messages": [
                    {
                        "id": message.id,
                        "role": message.role.value,
                        "content": message.content,
                        "token_count": message.token_count,
                        "created_at": message.created_at.isoformat(),
                    }
                    for message in session_messages_map.get(session.id, [])
                ],
            }
            for session in sessions
        ],
    }
