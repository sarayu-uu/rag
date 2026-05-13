"""
Telemetry helpers for metrics_usage write + read flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.mysql import MetricUsage, RequestType, Role, RoleName, User, check_db_connection
from app.retrieval.chroma_store import vector_store_health

DEFAULT_INPUT_TOKEN_COST = Decimal("0.0000005")
DEFAULT_OUTPUT_TOKEN_COST = Decimal("0.0000015")


@dataclass(frozen=True)
class TelemetryWritePayload:
    request_type: RequestType
    user_id: int | None
    session_id: int | None
    request_count: int
    token_input: int
    token_output: int
    token_total: int
    estimated_cost: Decimal
    latency_ms: int
    ingestion_time_ms: int | None
    retrieval_latency_ms: int | None
    model_latency_ms: int | None
    error_count: int


# Starts a precise timer for one request so we can measure end-to-end latency.
def now_perf() -> float:
    return perf_counter()


# Converts the elapsed time since `start` into milliseconds for telemetry fields.
def elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


# Maps URL paths to a small set of request categories used in dashboards and summaries.
def classify_request_type(path: str) -> RequestType | None:
    if path.startswith("/chat"):
        return RequestType.CHAT
    if path.startswith("/retrieval"):
        return RequestType.RETRIEVAL
    if path.startswith("/ingestion") or path.startswith("/documents") or path.startswith("/admin"):
        return RequestType.INGESTION
    return None


# Safely parses string-like values into ints and returns None when parsing fails.
def safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# Estimates token usage from text length when exact model token data is not available.
def estimate_token_count(text: str) -> int:
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return max(1, len(cleaned) // 4)


# Estimates request cost from input/output token counts using configured per-token rates.
def estimate_cost(token_input: int, token_output: int) -> Decimal:
    return (
        Decimal(token_input) * DEFAULT_INPUT_TOKEN_COST
        + Decimal(token_output) * DEFAULT_OUTPUT_TOKEN_COST
    ).quantize(Decimal("0.000001"))


# Builds one normalized telemetry payload from request path, response headers, and status.
# This is where defaults/fallbacks are applied when some headers are missing.
def build_write_payload(
    *,
    path: str,
    user_id: int | None,
    status_code: int,
    latency_ms: int,
    headers: dict[str, str],
) -> TelemetryWritePayload | None:
    request_type = classify_request_type(path)
    if request_type is None:
        return None

    session_id = safe_int(headers.get("x-telemetry-session-id"))
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

    if ingestion_time_ms is None and request_type == RequestType.INGESTION:
        ingestion_time_ms = latency_ms

    return TelemetryWritePayload(
        request_type=request_type,
        user_id=user_id,
        session_id=session_id,
        request_count=1,
        token_input=token_input,
        token_output=token_output,
        token_total=token_total,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
        ingestion_time_ms=ingestion_time_ms,
        retrieval_latency_ms=retrieval_latency_ms,
        model_latency_ms=model_latency_ms,
        error_count=1 if status_code >= 500 else 0,
    )


# Persists a single telemetry row into `metrics_usage` and commits immediately.
def write_metric_usage(db: Session, payload: TelemetryWritePayload) -> None:
    row = MetricUsage(
        user_id=payload.user_id,
        session_id=payload.session_id,
        request_type=payload.request_type,
        request_count=payload.request_count,
        token_input=payload.token_input,
        token_output=payload.token_output,
        token_total=payload.token_total,
        estimated_cost=payload.estimated_cost,
        latency_ms=payload.latency_ms,
        ingestion_time_ms=payload.ingestion_time_ms,
        retrieval_latency_ms=payload.retrieval_latency_ms,
        model_latency_ms=payload.model_latency_ms,
        error_count=payload.error_count,
    )
    db.add(row)
    db.commit()


# Applies role-based visibility rules to telemetry queries:
# - Admin: global data
# - Manager: team data (manager + assigned analysts)
# - Others: own data only
def _apply_scope(statement, *, current_user: User):
    role_name = current_user.role.name if current_user.role else None
    if role_name is None:
        return statement.where(MetricUsage.user_id == current_user.id), "current_user"

    if role_name == RoleName.ADMIN:
        return statement, "global"
    if role_name == RoleName.MANAGER:
        team_user_ids_stmt = (
            select(User.id)
            .where(
                or_(
                    User.id == current_user.id,
                    and_(
                        User.manager_user_id == current_user.id,
                        User.role.has(Role.name == RoleName.ANALYST),
                        User.is_active.is_(True),
                        User.is_deleted.is_(False),
                    ),
                )
            )
        )
        return statement.where(MetricUsage.user_id.in_(team_user_ids_stmt)), "team"
    return statement.where(MetricUsage.user_id == current_user.id), "current_user"


# Builds the telemetry summary response for the requested time window.
# It aggregates usage, error, latency, and cost stats, then attaches DB/vector health signals.
def build_telemetry_summary(db: Session, *, current_user: User, hours: int = 24) -> dict[str, Any]:
    hours = max(1, min(hours, 24 * 30))
    from_ts = datetime.utcnow() - timedelta(hours=hours)

    totals_stmt = select(
        func.coalesce(func.sum(MetricUsage.request_count), 0),
        func.coalesce(func.sum(MetricUsage.error_count), 0),
        func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        func.coalesce(func.max(MetricUsage.latency_ms), 0),
        func.coalesce(func.sum(MetricUsage.token_input), 0),
        func.coalesce(func.sum(MetricUsage.token_output), 0),
        func.coalesce(func.sum(MetricUsage.token_total), 0),
        func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
        func.coalesce(func.avg(MetricUsage.ingestion_time_ms), 0),
        func.coalesce(func.avg(MetricUsage.retrieval_latency_ms), 0),
        func.coalesce(func.avg(MetricUsage.model_latency_ms), 0),
    ).where(MetricUsage.created_at >= from_ts)
    totals_stmt, scope = _apply_scope(totals_stmt, current_user=current_user)
    totals = db.execute(totals_stmt).one()

    by_type_stmt = (
        select(
            MetricUsage.request_type,
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
        )
        .where(MetricUsage.created_at >= from_ts)
        .group_by(MetricUsage.request_type)
        .order_by(MetricUsage.request_type.asc())
    )
    by_type_stmt, _ = _apply_scope(by_type_stmt, current_user=current_user)
    by_type_rows = db.execute(by_type_stmt).all()

    per_user_stmt = (
        select(
            MetricUsage.user_id,
            User.username,
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        )
        .outerjoin(User, User.id == MetricUsage.user_id)
        .where(MetricUsage.created_at >= from_ts)
        .group_by(MetricUsage.user_id, User.username)
        .order_by(func.sum(MetricUsage.request_count).desc())
        .limit(25)
    )
    per_user_stmt, _ = _apply_scope(per_user_stmt, current_user=current_user)
    per_user_rows = db.execute(per_user_stmt).all()

    db_status = "connected"
    db_detail = None
    try:
        check_db_connection()
    except Exception as exc:
        db_status = "disconnected"
        db_detail = str(exc)

    vector = vector_store_health()
    request_count = int(totals[0] or 0)
    error_count = int(totals[1] or 0)
    error_rate = (error_count / request_count) if request_count else 0.0

    return {
        "status": "success",
        "window_hours": hours,
        "scope": scope,
        "logging": {
            "request_count": request_count,
            "error_count": error_count,
            "error_rate": round(error_rate, 4),
            "avg_latency_ms": round(float(totals[2] or 0), 2),
            "max_latency_ms": int(totals[3] or 0),
        },
        "usage_tracking": {
            "token_input": int(totals[4] or 0),
            "token_output": int(totals[5] or 0),
            "token_total": int(totals[6] or 0),
            "estimated_cost": round(float(totals[7] or 0), 6),
            "by_request_type": [
                {
                    "request_type": row[0].value if isinstance(row[0], RequestType) else str(row[0]),
                    "request_count": int(row[1] or 0),
                    "error_count": int(row[2] or 0),
                    "avg_latency_ms": round(float(row[3] or 0), 2),
                    "token_total": int(row[4] or 0),
                }
                for row in by_type_rows
            ],
            "per_user_usage": [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "request_count": int(row[2] or 0),
                    "error_count": int(row[3] or 0),
                    "token_total": int(row[4] or 0),
                    "estimated_cost": round(float(row[5] or 0), 6),
                    "avg_latency_ms": round(float(row[6] or 0), 2),
                }
                for row in per_user_rows
            ],
        },
        "model_performance": {
            "avg_ingestion_time_ms": round(float(totals[8] or 0), 2),
            "avg_retrieval_latency_ms": round(float(totals[9] or 0), 2),
            "avg_model_latency_ms": round(float(totals[10] or 0), 2),
        },
        "system_health_monitoring": {
            "api_status": "ok",
            "database": db_status,
            "database_detail": db_detail,
            "vector_store": vector.get("status"),
            "vector_collection": vector.get("collection"),
            "vector_detail": vector.get("detail"),
            "sampled_at_utc": datetime.utcnow().isoformat(),
        },
    }


