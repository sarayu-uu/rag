"""
Telemetry routes for Phase 10 observability and metrics.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.mysql import RequestType, get_db
from app.telemetry.service import (
    build_metrics_summary,
    build_request_type_summary,
    build_user_usage_summary,
    list_metrics_rows,
)

router = APIRouter(tags=["telemetry"])


@router.get("/metrics", summary="Phase 10: Aggregated telemetry, observability, and usage metrics")
def get_metrics(
    hours: int = Query(default=24, ge=1, le=24 * 30, description="Time window in hours."),
    user_id: int | None = Query(default=None, ge=1, description="Optional user-level filter."),
    request_type: RequestType | None = Query(default=None, description="Optional request type filter."),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return {
            "status": "success",
            "metrics": build_metrics_summary(
                db,
                hours=hours,
                user_id=user_id,
                request_type=request_type,
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"metrics endpoint failed: {exc}") from exc


@router.get("/metrics/raw", summary="Phase 10: Recent raw rows from metrics_usage")
def get_metrics_raw(
    hours: int = Query(default=24, ge=1, le=24 * 30, description="Time window in hours."),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum rows to return."),
    user_id: int | None = Query(default=None, ge=1, description="Optional user-level filter."),
    request_type: RequestType | None = Query(default=None, description="Optional request type filter."),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return {
            "status": "success",
            "rows": list_metrics_rows(
                db,
                hours=hours,
                limit=limit,
                user_id=user_id,
                request_type=request_type,
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"metrics/raw endpoint failed: {exc}") from exc


@router.get("/metrics/users", summary="Phase 10: Per-user usage and error summary")
def get_metrics_users(
    hours: int = Query(default=24, ge=1, le=24 * 30, description="Time window in hours."),
    limit: int = Query(default=25, ge=1, le=100, description="Top users limit."),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return {
            "status": "success",
            "users": build_user_usage_summary(
                db,
                hours=hours,
                limit=limit,
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"metrics/users endpoint failed: {exc}") from exc


@router.get("/metrics/request-types", summary="Phase 10: Usage summary by request type")
def get_metrics_request_types(
    hours: int = Query(default=24, ge=1, le=24 * 30, description="Time window in hours."),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return {
            "status": "success",
            "request_types": build_request_type_summary(
                db,
                hours=hours,
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"metrics/request-types endpoint failed: {exc}") from exc
