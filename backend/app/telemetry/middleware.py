"""
Request telemetry middleware for Phase 10.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from time import perf_counter

from fastapi import Request

from app.models.mysql import SessionLocal
from app.telemetry.service import build_context_from_headers, record_metric_usage

logger = logging.getLogger("app.telemetry")

SKIP_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)


async def telemetry_middleware(request: Request, call_next):
    path = request.url.path
    start = perf_counter()

    if path.startswith(SKIP_PATH_PREFIXES):
        return await call_next(request)

    status_code = 500
    response_headers: dict[str, str] = {}

    try:
        response = await call_next(request)
        status_code = response.status_code
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        return response
    except Exception:
        logger.exception(
            "Unhandled error for %s %s",
            request.method,
            path,
        )
        raise
    finally:
        latency_ms = int((perf_counter() - start) * 1000)
        context = build_context_from_headers(path, response_headers)

        if context.request_type is not None:
            # Fallback: for ingestion endpoints, total request latency is a safe ingestion time proxy.
            if context.ingestion_time_ms is None and path.startswith("/ingestion"):
                context = replace(context, ingestion_time_ms=latency_ms)

            with SessionLocal() as db:
                try:
                    record_metric_usage(
                        db,
                        context=context,
                        latency_ms=latency_ms,
                        status_code=status_code,
                    )
                except Exception:
                    logger.exception("Failed to persist metrics_usage row for %s %s", request.method, path)

            level = logging.ERROR if status_code >= 400 else logging.INFO
            logger.log(
                level,
                "request=%s %s status=%s latency_ms=%s",
                request.method,
                path,
                status_code,
                latency_ms,
            )
