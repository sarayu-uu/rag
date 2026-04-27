"""
Telemetry service utilities for Phase 10 metrics collection and aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import mean
from typing import Any

from sqlalchemy import Select, String, cast, func, select
from sqlalchemy.orm import Session

from app.models.mysql import MetricUsage, RequestType, check_db_connection
from app.retrieval.chroma_store import vector_store_health

# Conservative placeholder rates for rough cost estimation until model-specific pricing is wired.
DEFAULT_INPUT_TOKEN_COST = Decimal("0.0000005")
DEFAULT_OUTPUT_TOKEN_COST = Decimal("0.0000015")


@dataclass(frozen=True)
class TelemetryContext:
    request_type: RequestType | None
    session_id: int | None
    user_id: int | None
    token_input: int
    token_output: int
    token_total: int
    estimated_cost: Decimal
    ingestion_time_ms: int | None
    retrieval_latency_ms: int | None
    model_latency_ms: int | None


def classify_request_type(path: str) -> RequestType | None:
    if path.startswith("/chat"):
        return RequestType.CHAT
    if path.startswith("/retrieval"):
        return RequestType.RETRIEVAL
    if path.startswith("/ingestion"):
        return RequestType.INGESTION
    return None


def safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def estimate_token_count(text: str) -> int:
    # Lightweight approximation: ~4 chars/token on average for English.
    return max(1, len(text) // 4) if text else 0


def estimate_cost(token_input: int, token_output: int) -> Decimal:
    return (
        Decimal(token_input) * DEFAULT_INPUT_TOKEN_COST
        + Decimal(token_output) * DEFAULT_OUTPUT_TOKEN_COST
    ).quantize(Decimal("0.000001"))


def build_context_from_headers(path: str, headers: dict[str, str]) -> TelemetryContext:
    request_type = classify_request_type(path)
    session_id = safe_int(headers.get("x-telemetry-session-id"))
    user_id = safe_int(headers.get("x-telemetry-user-id"))

    token_input = safe_int(headers.get("x-telemetry-token-input")) or 0
    token_output = safe_int(headers.get("x-telemetry-token-output")) or 0
    token_total = safe_int(headers.get("x-telemetry-token-total")) or (token_input + token_output)

    estimated_cost_header = headers.get("x-telemetry-estimated-cost")
    if estimated_cost_header:
        try:
            estimated_cost = Decimal(estimated_cost_header)
        except Exception:
            estimated_cost = estimate_cost(token_input, token_output)
    else:
        estimated_cost = estimate_cost(token_input, token_output)

    ingestion_time_ms = safe_int(headers.get("x-telemetry-ingestion-time-ms"))
    retrieval_latency_ms = safe_int(headers.get("x-telemetry-retrieval-latency-ms"))
    model_latency_ms = safe_int(headers.get("x-telemetry-model-latency-ms"))

    return TelemetryContext(
        request_type=request_type,
        session_id=session_id,
        user_id=user_id,
        token_input=token_input,
        token_output=token_output,
        token_total=token_total,
        estimated_cost=estimated_cost,
        ingestion_time_ms=ingestion_time_ms,
        retrieval_latency_ms=retrieval_latency_ms,
        model_latency_ms=model_latency_ms,
    )


def record_metric_usage(
    db: Session,
    *,
    context: TelemetryContext,
    latency_ms: int,
    status_code: int,
) -> None:
    if context.request_type is None:
        return

    row = MetricUsage(
        user_id=context.user_id,
        session_id=context.session_id,
        request_type=context.request_type,
        request_count=1,
        token_input=context.token_input,
        token_output=context.token_output,
        token_total=context.token_total,
        estimated_cost=context.estimated_cost,
        latency_ms=latency_ms,
        ingestion_time_ms=context.ingestion_time_ms,
        retrieval_latency_ms=context.retrieval_latency_ms,
        model_latency_ms=context.model_latency_ms,
        error_count=1 if status_code >= 400 else 0,
    )
    db.add(row)
    db.commit()


def _apply_time_filters(
    query: Select[Any],
    *,
    from_ts: datetime | None,
    to_ts: datetime | None,
    user_id: int | None,
    request_type: RequestType | None,
) -> Select[Any]:
    if from_ts is not None:
        query = query.where(MetricUsage.created_at >= from_ts)
    if to_ts is not None:
        query = query.where(MetricUsage.created_at <= to_ts)
    if user_id is not None:
        query = query.where(MetricUsage.user_id == user_id)
    if request_type is not None:
        # Support both enum name (CHAT) and value (chat) in legacy rows.
        query = query.where(
            cast(MetricUsage.request_type, String).in_([request_type.name, request_type.value])
        )
    return query


def _compute_percentile(values: list[int], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(round((percentile / 100.0) * (len(sorted_values) - 1)))
    return float(sorted_values[index])


def build_metrics_summary(
    db: Session,
    *,
    hours: int,
    user_id: int | None,
    request_type: RequestType | None,
) -> dict[str, Any]:
    hours = max(1, min(hours, 24 * 30))
    from_ts = datetime.utcnow() - timedelta(hours=hours)

    totals_query = _apply_time_filters(
        select(
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.sum(MetricUsage.token_input), 0),
            func.coalesce(func.sum(MetricUsage.token_output), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        ),
        from_ts=from_ts,
        to_ts=None,
        user_id=user_id,
        request_type=request_type,
    )
    (
        request_count,
        error_count,
        token_input,
        token_output,
        token_total,
        estimated_cost,
        avg_latency_ms,
    ) = db.execute(totals_query).one()

    latency_query = _apply_time_filters(
        select(MetricUsage.latency_ms),
        from_ts=from_ts,
        to_ts=None,
        user_id=user_id,
        request_type=request_type,
    )
    latency_values = [int(value) for value in db.scalars(latency_query).all() if value is not None]

    component_query = _apply_time_filters(
        select(
            MetricUsage.ingestion_time_ms,
            MetricUsage.retrieval_latency_ms,
            MetricUsage.model_latency_ms,
        ),
        from_ts=from_ts,
        to_ts=None,
        user_id=user_id,
        request_type=request_type,
    )
    component_rows = db.execute(component_query).all()
    ingestion_values = [int(row[0]) for row in component_rows if row[0] is not None]
    retrieval_values = [int(row[1]) for row in component_rows if row[1] is not None]
    model_values = [int(row[2]) for row in component_rows if row[2] is not None]

    per_type_query = _apply_time_filters(
        select(
            cast(MetricUsage.request_type, String).label("request_type"),
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
        ).group_by(cast(MetricUsage.request_type, String)),
        from_ts=from_ts,
        to_ts=None,
        user_id=user_id,
        request_type=request_type,
    )
    per_type = [
        {
            "request_type": str(row[0]) if row[0] is not None else None,
            "request_count": int(row[1] or 0),
            "error_count": int(row[2] or 0),
            "avg_latency_ms": round(float(row[3] or 0), 2),
            "token_total": int(row[4] or 0),
        }
        for row in db.execute(per_type_query).all()
    ]

    per_user_query = _apply_time_filters(
        select(
            MetricUsage.user_id,
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        )
        .group_by(MetricUsage.user_id)
        .order_by(func.sum(MetricUsage.token_total).desc())
        .limit(25),
        from_ts=from_ts,
        to_ts=None,
        user_id=user_id,
        request_type=request_type,
    )
    per_user_usage = [
        {
            "user_id": row[0],
            "request_count": int(row[1] or 0),
            "error_count": int(row[2] or 0),
            "token_total": int(row[3] or 0),
            "estimated_cost": float(row[4] or 0),
            "avg_latency_ms": round(float(row[5] or 0), 2),
        }
        for row in db.execute(per_user_query).all()
    ]

    error_rate = (float(error_count) / float(request_count)) if request_count else 0.0
    db_status = "connected"
    db_detail = None
    try:
        check_db_connection()
    except Exception as exc:
        db_status = "disconnected"
        db_detail = str(exc)

    vector_status = vector_store_health()

    # Explicitly expose these as "not yet measured" until labeled eval data/feedback exists.
    evaluation_metrics = {
        "retrieval_precision": None,
        "retrieval_recall": None,
        "response_relevance": None,
        "note": "Requires labeled evaluation dataset and/or human feedback labels.",
    }

    return {
        "window_hours": hours,
        "from_utc": from_ts.isoformat(),
        "totals": {
            "request_count": int(request_count or 0),
            "error_count": int(error_count or 0),
            "error_rate": round(error_rate, 4),
            "token_input": int(token_input or 0),
            "token_output": int(token_output or 0),
            "token_total": int(token_total or 0),
            "estimated_cost": float(estimated_cost or 0),
            "avg_latency_ms": round(float(avg_latency_ms or 0), 2),
            "p50_latency_ms": _compute_percentile(latency_values, 50.0),
            "p95_latency_ms": _compute_percentile(latency_values, 95.0),
        },
        "latency_breakdown": {
            "avg_ingestion_time_ms": round(mean(ingestion_values), 2) if ingestion_values else 0.0,
            "avg_retrieval_latency_ms": round(mean(retrieval_values), 2) if retrieval_values else 0.0,
            "avg_model_latency_ms": round(mean(model_values), 2) if model_values else 0.0,
        },
        "usage_breakdown": {
            "per_request_type": per_type,
            "per_user_usage": per_user_usage,
        },
        "observability": {
            "application_logs": "Enabled via standard logging handlers.",
            "request_logs": "Enabled via telemetry middleware.",
            "error_logs": "Enabled via telemetry middleware.",
            "health_checks": ["/health", "/metrics"],
        },
        "system_monitoring": {
            "database": db_status,
            "database_detail": db_detail,
            "vector_store": vector_status.get("status"),
            "vector_collection": vector_status.get("collection"),
            "vector_detail": vector_status.get("detail"),
        },
        "evaluation_metrics": evaluation_metrics,
    }


def list_metrics_rows(
    db: Session,
    *,
    hours: int,
    limit: int,
    user_id: int | None,
    request_type: RequestType | None,
) -> list[dict[str, Any]]:
    hours = max(1, min(hours, 24 * 30))
    limit = max(1, min(limit, 500))
    from_ts = datetime.utcnow() - timedelta(hours=hours)

    query = _apply_time_filters(
        select(
            MetricUsage.id,
            MetricUsage.created_at,
            MetricUsage.user_id,
            MetricUsage.session_id,
            cast(MetricUsage.request_type, String).label("request_type"),
            MetricUsage.request_count,
            MetricUsage.error_count,
            MetricUsage.latency_ms,
            MetricUsage.ingestion_time_ms,
            MetricUsage.retrieval_latency_ms,
            MetricUsage.model_latency_ms,
            MetricUsage.token_input,
            MetricUsage.token_output,
            MetricUsage.token_total,
            MetricUsage.estimated_cost,
        )
        .order_by(MetricUsage.created_at.desc(), MetricUsage.id.desc())
        .limit(limit),
        from_ts=from_ts,
        to_ts=None,
        user_id=user_id,
        request_type=request_type,
    )
    rows = db.execute(query).all()
    return [
        {
            "id": row[0],
            "created_at": row[1].isoformat() if row[1] else None,
            "user_id": row[2],
            "session_id": row[3],
            "request_type": str(row[4]) if row[4] is not None else None,
            "request_count": row[5],
            "error_count": row[6],
            "latency_ms": row[7],
            "ingestion_time_ms": row[8],
            "retrieval_latency_ms": row[9],
            "model_latency_ms": row[10],
            "token_input": row[11],
            "token_output": row[12],
            "token_total": row[13],
            "estimated_cost": float(row[14] or 0),
        }
        for row in rows
    ]


def build_user_usage_summary(
    db: Session,
    *,
    hours: int,
    limit: int,
) -> list[dict[str, Any]]:
    hours = max(1, min(hours, 24 * 30))
    limit = max(1, min(limit, 100))
    from_ts = datetime.utcnow() - timedelta(hours=hours)

    query = _apply_time_filters(
        select(
            MetricUsage.user_id,
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        )
        .group_by(MetricUsage.user_id)
        .order_by(func.sum(MetricUsage.request_count).desc())
        .limit(limit),
        from_ts=from_ts,
        to_ts=None,
        user_id=None,
        request_type=None,
    )
    return [
        {
            "user_id": row[0],
            "request_count": int(row[1] or 0),
            "error_count": int(row[2] or 0),
            "token_total": int(row[3] or 0),
            "estimated_cost": float(row[4] or 0),
            "avg_latency_ms": round(float(row[5] or 0), 2),
        }
        for row in db.execute(query).all()
    ]


def build_request_type_summary(
    db: Session,
    *,
    hours: int,
) -> list[dict[str, Any]]:
    hours = max(1, min(hours, 24 * 30))
    from_ts = datetime.utcnow() - timedelta(hours=hours)

    query = _apply_time_filters(
        select(
            cast(MetricUsage.request_type, String).label("request_type"),
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
        )
        .group_by(cast(MetricUsage.request_type, String))
        .order_by(func.sum(MetricUsage.request_count).desc()),
        from_ts=from_ts,
        to_ts=None,
        user_id=None,
        request_type=None,
    )
    return [
        {
            "request_type": str(row[0]) if row[0] is not None else None,
            "request_count": int(row[1] or 0),
            "error_count": int(row[2] or 0),
            "avg_latency_ms": round(float(row[3] or 0), 2),
            "token_total": int(row[4] or 0),
            "estimated_cost": float(row[5] or 0),
        }
        for row in db.execute(query).all()
    ]
