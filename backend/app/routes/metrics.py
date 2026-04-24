"""
File purpose:
- Exposes a simple metrics summary endpoint for frontend dashboards and diagnostics.
- Aggregates the existing metrics_usage table without requiring a separate telemetry stack.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.mysql import MetricUsage, RequestType, get_db

router = APIRouter(tags=["metrics"])


def _to_float(value: Decimal | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


@router.get("/metrics", summary="Phase 12: Aggregate metrics and telemetry counters")
def get_metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    totals = db.execute(
        select(
            func.count(MetricUsage.id),
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.token_input), 0),
            func.coalesce(func.sum(MetricUsage.token_output), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
            func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
        )
    ).one()

    by_request_type_rows = db.execute(
        select(
            MetricUsage.request_type,
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        )
        .group_by(MetricUsage.request_type)
        .order_by(MetricUsage.request_type.asc())
    ).all()

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
    }
