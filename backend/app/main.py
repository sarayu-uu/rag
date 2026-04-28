"""
File purpose:
- FastAPI application entry point.
- Registers API routers and exposes the app object for Uvicorn.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import CORS_ORIGINS
from app.models.mysql import check_db_connection, init_db
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.ingestion_steps import router as ingestion_steps_router
from app.routes.metrics import router as metrics_router
from app.routes.retrieval import router as retrieval_router
from app.routes.test_eval import router as test_eval_router
from app.retrieval.chroma_store import vector_store_health
from app.telemetry.middleware import telemetry_middleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_ready = False
    app.state.database_error = None
    app.state.vector_store_ready = None
    app.state.vector_store_error = None

    try:
        init_db()
        app.state.database_ready = True
    except Exception as exc:
        app.state.database_error = str(exc)
        logger.warning("Database bootstrap failed during startup: %s", exc)

    yield

app = FastAPI(
    title="RAG Ingestion API",
    version="1.0.0",
    description="Upload and ingest supported files into normalized text.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(telemetry_middleware)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(ingestion_steps_router)
app.include_router(retrieval_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(metrics_router)
app.include_router(test_eval_router)


@app.get("/", tags=["system"])
async def root():
    return {"message": "RAG Ingestion API is running", "docs": "/docs"}


@app.get("/health", tags=["system"])
async def health(include_vector_store: bool = False):
    database_status = {"status": "ok", "database": "connected"}
    try:
        check_db_connection()
        app.state.database_ready = True
        app.state.database_error = None
    except Exception as exc:
        app.state.database_ready = False
        app.state.database_error = str(exc)
        database_status = {
            "status": "degraded",
            "database": "disconnected",
            "detail": str(exc),
        }

    vector_status: dict[str, str | None] = {"status": "not_checked", "collection": None, "detail": None}
    if include_vector_store:
        vector_status = vector_store_health()
        app.state.vector_store_ready = vector_status["status"] == "connected"
        app.state.vector_store_error = None if app.state.vector_store_ready else vector_status.get("detail")

    overall_status = "ok"
    if database_status["status"] != "ok":
        overall_status = "degraded"
    elif include_vector_store and vector_status["status"] != "connected":
        overall_status = "degraded"

    return {
        "status": overall_status,
        "database": database_status["database"],
        "database_detail": database_status.get("detail"),
        "vector_store": vector_status["status"],
        "vector_collection": vector_status.get("collection"),
        "vector_detail": vector_status.get("detail"),
    }
