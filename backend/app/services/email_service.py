"""
File purpose:
- Sends transactional emails for auth flows such as OTP verification.
- Keeps SMTP logic separate from route handlers.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from fastapi import HTTPException

from app.config.settings import (
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_TLS,
)


def is_smtp_configured() -> bool:
    return all([SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL])


def send_signup_otp_email(recipient_email: str, otp: str, expiry_minutes: int) -> None:
    if not is_smtp_configured():
        raise HTTPException(
            status_code=500,
            detail="SMTP is not configured on the server. Add SMTP settings to backend/.env.",
        )

    message = EmailMessage()
    message["Subject"] = "Your OTP for RAG Workspace"
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "Welcome to RAG Workspace.",
                "",
                f"Your OTP is: {otp}",
                f"This code expires in {expiry_minutes} minutes.",
                "",
                "If you did not try to create this account, you can ignore this email.",
            ]
        )
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    except smtplib.SMTPException as exc:
        raise HTTPException(status_code=502, detail="Failed to send OTP email.") from exc
