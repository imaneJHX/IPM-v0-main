"""FastAPI application factory — CORS, lifespan, and router registration."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.database import engine
from app.models.business_need import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def _run_post_startup_tasks() -> None:
    """Run heavy non-critical startup work without blocking API readiness."""
    # 1. Warm up embedding model (can be slow on first run due to model download)
    try:
        from app.core.embedding_client import _get_local_model

        await asyncio.to_thread(_get_local_model)
        logger.info("Embedding model warmed up.")
    except Exception as exc:
        logger.warning("Embedding model warmup failed (non-fatal): %s", exc)

    # 2. Seed ChromaDB with synthetic data
    try:
        from app.seeds.seed_chroma import seed_chromadb

        await asyncio.to_thread(seed_chromadb)
    except Exception as exc:
        logger.warning("ChromaDB seeding failed (non-fatal): %s", exc)

    # 3. Seed DXC product catalog into dxc_catalog collection
    try:
        from app.core.seed_catalog import seed_catalog

        await asyncio.to_thread(seed_catalog)
    except Exception as exc:
        logger.warning("Catalog seeding failed (non-fatal): %s", exc)

    # 4. Ensure MinIO bucket exists
    try:
        from app.core.minio_client import ensure_bucket

        await asyncio.to_thread(ensure_bucket)
        logger.info("MinIO bucket ensured.")
    except Exception as exc:
        logger.warning("MinIO bucket creation failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle events."""
    logger.info("Starting IPM API...")

    # 1. Create database tables (dev convenience — production uses Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured.")

    # Run heavy non-critical startup work in background.
    asyncio.create_task(_run_post_startup_tasks())

    logger.info("IPM API ready.")
    yield

    # Shutdown
    await engine.dispose()
    logger.info("IPM API shutdown complete.")


app = FastAPI(
    title="IPM — Innovation Progress Model",
    description="Phase 1 Sourcing API for business needs intake and pipeline management.",
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routes ---
app.include_router(api_v1_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple health status."""
    return {"status": "ok"}
