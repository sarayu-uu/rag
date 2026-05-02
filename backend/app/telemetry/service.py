"""
Telemetry helpers for metrics_usage write + read flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.mysql import MetricUsage, RequestType, User, check_db_connection
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


# Detailed function explanation:
# - Purpose: `now_perf` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def now_perf() -> float:
    return perf_counter()


# Detailed function explanation:
# - Purpose: `elapsed_ms` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


# Detailed function explanation:
# - Purpose: `classify_request_type` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def classify_request_type(path: str) -> RequestType | None:
    if path.startswith("/chat"):
        return RequestType.CHAT
    if path.startswith("/retrieval"):
        return RequestType.RETRIEVAL
    if path.startswith("/ingestion") or path.startswith("/documents"):
        return RequestType.INGESTION
    return None


# Detailed function explanation:
# - Purpose: `safe_int` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# Detailed function explanation:
# - Purpose: `estimate_token_count` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def estimate_token_count(text: str) -> int:
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    return max(1, len(cleaned) // 4)


# Detailed function explanation:
# - Purpose: `estimate_cost` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def estimate_cost(token_input: int, token_output: int) -> Decimal:
    return (
        Decimal(token_input) * DEFAULT_INPUT_TOKEN_COST
        + Decimal(token_output) * DEFAULT_OUTPUT_TOKEN_COST
    ).quantize(Decimal("0.000001"))


# Detailed function explanation:
# - Purpose: `build_write_payload` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
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
        error_count=1 if status_code >= 400 else 0,
    )


# Detailed function explanation:
# - Purpose: `write_metric_usage` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
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


# Detailed function explanation:
# - Purpose: `_apply_scope` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
def _apply_scope(statement, *, current_user: User):
    role_name = current_user.role.name if current_user.role else None
    if role_name is None:
        return statement.where(MetricUsage.user_id == current_user.id), "current_user"

    if role_name.value in {"Admin", "Manager"}:
        return statement, "global"
    return statement.where(MetricUsage.user_id == current_user.id), "current_user"


# Detailed function explanation:
# - Purpose: `build_telemetry_summary` handles one focused step of this module's workflow.
# - Usage in flow: Called by routes/services/helpers to keep the logic modular and reusable.
# - Input/Output intent: Validates/normalizes inputs, performs its task, and returns predictable output
#   (or raises a clear exception) so downstream code can continue reliably.
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
            func.coalesce(func.sum(MetricUsage.request_count), 0),
            func.coalesce(func.sum(MetricUsage.error_count), 0),
            func.coalesce(func.sum(MetricUsage.token_total), 0),
            func.coalesce(func.sum(MetricUsage.estimated_cost), 0),
            func.coalesce(func.avg(MetricUsage.latency_ms), 0),
        )
        .where(MetricUsage.created_at >= from_ts)
        .group_by(MetricUsage.user_id)
        .order_by(func.sum(MetricUsage.request_count).desc())
        .limit(25)
    )
    if scope != "global":
        per_user_stmt = per_user_stmt.where(MetricUsage.user_id == current_user.id)
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
                    "request_count": int(row[1] or 0),
                    "error_count": int(row[2] or 0),
                    "token_total": int(row[3] or 0),
                    "estimated_cost": round(float(row[4] or 0), 6),
                    "avg_latency_ms": round(float(row[5] or 0), 2),
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
