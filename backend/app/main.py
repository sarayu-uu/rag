"""
File purpose:
- FastAPI application entry point.
- Registers API routers and exposes the app object for Uvicorn.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.upload import router as upload_router
from app.routes.ingestion_steps import router as ingestion_steps_router
from app.config.settings import CORS_ORIGINS

app = FastAPI(
    title="RAG Ingestion API",
    version="1.0.0",
    description="Upload and ingest supported files into normalized text.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(ingestion_steps_router)


@app.get("/", tags=["system"])
async def root():
    return {"message": "RAG Ingestion API is running", "docs": "/docs"}


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}
