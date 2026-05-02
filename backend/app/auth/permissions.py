"""
File purpose:
- Centralizes document permission checks for owner, role, and user grants.
- Keeps document listing, retrieval, and chat authorization consistent.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.mysql import Document, Permission, RoleName, User


# Detailed function explanation:
# - Purpose: `_has_global_document_access` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _has_global_document_access(user: User, *, permission_field: str) -> bool:
    role_name = user.role.name if user.role else None
    if role_name == RoleName.ADMIN:
        return True
    if role_name == RoleName.MANAGER:
        return permission_field != "can_edit"
    return False


# Detailed function explanation:
# - Purpose: `document_access_filter` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def document_access_filter(user: User, *, permission_field: str):
    if _has_global_document_access(user, permission_field=permission_field):
        return None

    role_id = user.role_id
    permission_column = getattr(Permission, permission_field)
    return or_(
        Document.upload_user_id == user.id,
        Document.id.in_(
            select(Permission.document_id).where(
                permission_column.is_(True),
                or_(
                    Permission.user_id == user.id,
                    Permission.role_id == role_id,
                ),
            )
        ),
    )


# Detailed function explanation:
# - Purpose: `accessible_document_ids` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def accessible_document_ids(db: Session, user: User, *, permission_field: str) -> list[int] | None:
    if _has_global_document_access(user, permission_field=permission_field):
        return None

    access_filter = document_access_filter(user, permission_field=permission_field)
    if access_filter is None:
        return None

    return list(db.scalars(select(Document.id).where(access_filter)).all())
