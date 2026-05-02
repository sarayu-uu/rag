"""
File purpose:
- Provides lightweight password hashing and JWT helpers for auth endpoints.
- Keeps auth utilities separate from route handlers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config.settings import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.models.mysql import RoleName, User, get_db

bearer_scheme = HTTPBearer(auto_error=False)


# Detailed function explanation:
# - Purpose: `hash_password` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Detailed function explanation:
# - Purpose: `verify_password` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# Detailed function explanation:
# - Purpose: `_create_token` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _create_token(*, user: User, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.name.value if user.role else None,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# Detailed function explanation:
# - Purpose: `create_access_token` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def create_access_token(user: User) -> str:
    return _create_token(
        user=user,
        token_type="access",
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


# Detailed function explanation:
# - Purpose: `create_refresh_token` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def create_refresh_token(user: User) -> str:
    return _create_token(
        user=user,
        token_type="refresh",
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


# Detailed function explanation:
# - Purpose: `decode_token` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc
    return payload


# Detailed function explanation:
# - Purpose: `get_current_user` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        )

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required.",
        )

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
        ) from exc

    user = db.scalar(
        select(User)
        .options(joinedload(User.role))
        .where(User.id == user_id)
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user was not found or is inactive.",
        )
    return user


# Detailed function explanation:
# - Purpose: `is_privileged_user` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def is_privileged_user(user: User) -> bool:
    role_name = user.role.name if user.role else None
    return role_name in {RoleName.ADMIN, RoleName.MANAGER}
