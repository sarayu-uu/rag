"""
File purpose:
- Exposes a simple metrics summary endpoint for frontend dashboards and diagnostics.
- Aggregates the existing metrics_usage table without requiring a separate telemetry stack.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import get_current_user, is_privileged_user
from app.models.mysql import MetricUsage, RequestType, User, get_db
from app.telemetry.service import build_telemetry_summary

router = APIRouter(tags=["metrics"])


# Detailed function explanation:
# - Purpose: `_to_float` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _to_float(value: Decimal | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


@router.get(
    "/metrics",
    summary="Phase 12: Aggregate metrics and telemetry counters",
    description="Usage: Used by frontend dashboards. Purpose: returns aggregated token, request, error, latency, and cost metrics.",
)
# Detailed function explanation:
# - Purpose: `get_metrics` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    totals_statement = select(
        func.count(MetricUsage.id),
        func.coalesce(func.sum(MetricUsage.request_count), 0),
        func.coalesce(func.sum(MetricUsage.token_input), 0),
        func.coalesce(func.sum(MetricUsage.token_output), 0),
        func.coalesce(func.sum(MetricUsage.token_total), 0),
        func.coalesce(func.sum(MetricUsage.error_count), 0),
        func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
    )
    by_request_type_statement = (
        select(
            MetricUsage.request_type,
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        )
        .group_by(MetricUsage.request_type)
        .order_by(MetricUsage.request_type.asc())
    )
    if not is_privileged_user(current_user):
        totals_statement = totals_statement.where(MetricUsage.user_id == current_user.id)
        by_request_type_statement = by_request_type_statement.where(MetricUsage.user_id == current_user.id)

    totals = db.execute(totals_statement).one()
    by_request_type_rows = db.execute(by_request_type_statement).all()

    by_request_type = {
        (request_type.value if isinstance(request_type, RequestType) else str(request_type)): {
            "request_count": int(request_count or 0),
            "token_total": int(token_total or 0),
            "avg_latency_ms": round(_to_float(avg_latency), 2),
        }
        for request_type, request_count, token_total, avg_latency in by_request_type_rows
    }

    return {
        "status": "success",
        "totals": {
            "metric_rows": int(totals[0] or 0),
            "request_count": int(totals[1] or 0),
            "token_input": int(totals[2] or 0),
            "token_output": int(totals[3] or 0),
            "token_total": int(totals[4] or 0),
            "error_count": int(totals[5] or 0),
            "avg_latency_ms": round(_to_float(totals[6]), 2),
            "estimated_cost": round(_to_float(totals[7]), 6),
        },
        "by_request_type": by_request_type,
        "scope": "global" if is_privileged_user(current_user) else "current_user",
    }


@router.get(
    "/telemetry",
    summary="Phase 10: Telemetry and observability summary from metrics_usage",
    description="Usage: Used by frontend telemetry page (admin/manager only). Purpose: detailed operational telemetry over a time window.",
)
# Detailed function explanation:
# - Purpose: `get_telemetry` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def get_telemetry(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if not is_privileged_user(current_user):
        raise HTTPException(status_code=403, detail="Telemetry is available only to admin and manager roles.")

    payload = build_telemetry_summary(
        db,
        current_user=current_user,
        hours=hours,
    )
    payload["generated_at_utc"] = datetime.utcnow().isoformat()
    return payload
