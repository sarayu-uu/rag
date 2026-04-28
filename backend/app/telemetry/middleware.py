"""
Telemetry write middleware for metrics_usage.
"""

from __future__ import annotations

import logging

from fastapi import Request

from app.auth.security import decode_token
from app.models.mysql import SessionLocal
from app.telemetry.service import (
    build_write_payload,
    elapsed_ms,
    now_perf,
    write_metric_usage,
)

logger = logging.getLogger("app.telemetry")


def _resolve_user_id_from_auth_header(request: Request) -> int | None:
    raw_auth = request.headers.get("authorization", "").strip()
    if not raw_auth.lower().startswith("bearer "):
        return None

    token = raw_auth.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        payload = decode_token(token)
    except Exception:
        return None

    if payload.get("type") != "access":
        return None

    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        return None


async def telemetry_middleware(request: Request, call_next):
    started = now_perf()
    path = request.url.path
    status_code = 500
    response_headers: dict[str, str] = {}
    user_id = _resolve_user_id_from_auth_header(request)

    try:
        response = await call_next(request)
        status_code = response.status_code
        response_headers = {k.lower(): v for k, v in response.headers.items()}
        return response
    except Exception:
        logger.exception("Unhandled backend error for %s %s", request.method, path)
        raise
    finally:
        latency_ms = elapsed_ms(started)
        payload = build_write_payload(
            path=path,
            user_id=user_id,
            status_code=status_code,
            latency_ms=latency_ms,
            headers=response_headers,
        )

        if payload is not None:
            with SessionLocal() as db:
                try:
                    write_metric_usage(db, payload)
                except Exception:
                    logger.exception("Failed writing metrics_usage row for %s %s", request.method, path)

        log_level = logging.ERROR if status_code >= 400 else logging.INFO
        logger.log(log_level, "request=%s %s status=%s latency_ms=%s", request.method, path, status_code, latency_ms)
