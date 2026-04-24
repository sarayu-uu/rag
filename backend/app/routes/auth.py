"""
File purpose:
- Exposes Phase 13 auth endpoints for signup, verification, login, refresh, and me.
- Uses JWT plus a development OTP flow so the app can operate before SMTP is added.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.mysql import Role, RoleName, User, get_db

router = APIRouter(prefix="/auth", tags=["auth"])

OTP_STORE: dict[str, dict[str, Any]] = {}
DEFAULT_SIGNUP_ROLE = RoleName.VIEWER
OTP_EXPIRY_MINUTES = 10


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class VerifyOtpRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    otp: str = Field(..., min_length=4, max_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


def _generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


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


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or "." not in email.split("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Provide a valid email address.")
    return email


def _get_signup_role(db: Session) -> Role:
    role = db.scalar(select(Role).where(Role.name == DEFAULT_SIGNUP_ROLE))
    if role is None:
        role = Role(name=DEFAULT_SIGNUP_ROLE, description="Default role for new signups.")
        db.add(role)
        db.flush()
    return role


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User)
        .options(joinedload(User.role))
        .where(User.email == email.strip().lower())
    )


@router.post("/signup", summary="Phase 13: Register a user and issue a development OTP")
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    normalized_email = _normalize_email(payload.email)
    existing_by_email = _get_user_by_email(db, normalized_email)
    if existing_by_email is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    existing_by_username = db.scalar(select(User).where(User.username == payload.username.strip()))
    if existing_by_username is not None:
        raise HTTPException(status_code=409, detail="A user with this username already exists.")

    role = _get_signup_role(db)
    user = User(
        username=payload.username.strip(),
        email=normalized_email,
        password_hash=hash_password(payload.password),
        role_id=role.id,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user = _get_user_by_email(db, user.email) or user

    otp = _generate_otp()
    OTP_STORE[user.email] = {
        "otp": otp,
        "user_id": user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(),
    }

    return {
        "status": "success",
        "message": "Signup successful. Verify the OTP to activate the account.",
        "user": _serialize_user(user),
        "otp_delivery": "development_inline",
        "otp": otp,
        "otp_expires_in_minutes": OTP_EXPIRY_MINUTES,
    }


@router.post("/verify-otp", summary="Phase 13: Verify a signup OTP and activate the account")
def verify_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    email = _normalize_email(payload.email)
    record = OTP_STORE.get(email)
    if record is None or record.get("otp") != payload.otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    expires_at_raw = record.get("expires_at")
    if expires_at_raw:
        expires_at = datetime.fromisoformat(str(expires_at_raw))
        if datetime.now(timezone.utc) > expires_at:
            OTP_STORE.pop(email, None)
            raise HTTPException(status_code=400, detail="OTP expired. Sign up again to request a fresh code.")

    user = db.get(User, int(record["user_id"]))
    if user is None:
        raise HTTPException(status_code=404, detail="User linked to this OTP was not found.")

    user.is_active = True
    db.commit()
    OTP_STORE.pop(email, None)
    user = _get_user_by_email(db, email) or user

    return {
        "status": "success",
        "message": "OTP verified successfully.",
        "user": _serialize_user(user),
    }


@router.post("/login", summary="Phase 13: Authenticate a verified user and issue JWTs")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = _get_user_by_email(db, _normalize_email(payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Verify OTP before logging in.")

    return {
        "status": "success",
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


@router.post("/refresh", summary="Phase 13: Exchange a refresh token for a new access token")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    token_payload = decode_token(payload.refresh_token)
    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required.")

    try:
        user_id = int(token_payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token subject.") from exc

    user = db.scalar(select(User).options(joinedload(User.role)).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Refresh token user is not available.")

    return {
        "status": "success",
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
    }


@router.get("/me", summary="Phase 13: Get the authenticated user profile")
def get_me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "status": "success",
        "user": _serialize_user(current_user),
    }
