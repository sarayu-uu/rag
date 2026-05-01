"""
File purpose:
- Exposes lightweight admin and RBAC endpoints for users and document permissions.
- Applies role checks using the current JWT-authenticated user.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.security import get_current_user
from app.models.mysql import Document, Permission, Role, RoleName, User, get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class UpdateUserRoleRequest(BaseModel):
    role: RoleName


class UpdateDocumentPermissionRequest(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    role_id: int | None = Field(default=None, gt=0)
    role: RoleName | None = None
    can_read: bool = False
    can_query: bool = False
    can_edit: bool = False


def _require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    role_name = current_user.role.name if current_user.role else None
    if role_name not in {RoleName.ADMIN, RoleName.MANAGER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager role required.",
        )
    return current_user


def _require_supervising_admin(current_user: User = Depends(get_current_user)) -> User:
    role_name = current_user.role.name if current_user.role else None
    if role_name != RoleName.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )
    return current_user


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.name.value if user.role else None,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


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


@router.get("/users", summary="Phase 12: List users for admin workflows")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin_user),
) -> dict[str, Any]:
    users = db.scalars(
        select(User)
        .options(joinedload(User.role))
        .order_by(User.created_at.desc(), User.id.desc())
    ).unique().all()
    return {
        "status": "success",
        "count": len(users),
        "users": [_serialize_user(user) for user in users],
    }


@router.patch("/users/{user_id}/role", summary="Phase 12: Update a user's RBAC role")
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin_user),
) -> dict[str, Any]:
    user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} was not found.")

    role = db.scalar(select(Role).where(Role.name == payload.role))
    if role is None:
        raise HTTPException(status_code=404, detail=f"Role {payload.role.value} was not found.")

    user.role_id = role.id
    db.commit()
    user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == user_id)) or user

    return {
        "status": "success",
        "message": "User role updated successfully.",
        "user": _serialize_user(user),
    }


@router.delete("/users/{user_id}", summary="Phase 12: Delete a non-admin user")
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

    serialized_user = _serialize_user(user)
    db.delete(user)
    db.commit()

    return {
        "status": "success",
        "message": "User deleted successfully.",
        "user": serialized_user,
    }


@router.patch("/documents/{document_id}/permissions", summary="Phase 12: Update one document permission rule")
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

    if payload.user_id is not None and db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} was not found.")

    role_id = payload.role_id
    if payload.role is not None:
        role = db.scalar(select(Role).where(Role.name == payload.role))
        if role is None:
            raise HTTPException(status_code=404, detail=f"Role {payload.role.value} was not found.")
        role_id = role.id
    elif role_id is not None and db.get(Role, role_id) is None:
        raise HTTPException(status_code=404, detail=f"Role {role_id} was not found.")

    if payload.user_id is None and role_id is None:
        raise HTTPException(status_code=400, detail="Provide either user_id or role for the permission rule.")

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
