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
from app.routes.ingestion_steps import router as ingestion_steps_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_ready = False
    app.state.database_error = None

    try:
        check_db_connection()
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

app.include_router(ingestion_steps_router)


@app.get("/", tags=["system"])
async def root():
    return {"message": "RAG Ingestion API is running", "docs": "/docs"}


@app.get("/health", tags=["system"])
async def health():
    try:
        check_db_connection()
        app.state.database_ready = True
        app.state.database_error = None
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        app.state.database_ready = False
        app.state.database_error = str(exc)
        return {
            "status": "degraded",
            "database": "disconnected",
            "detail": str(exc),
        }
