"""
ABOS — Adaptive Business Operating System
FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.db.session import init_db
from backend.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    setup_logging()
    await init_db()
    yield
    # teardown hooks go here if needed


def create_app() -> FastAPI:
    app = FastAPI(
        title="ABOS — Adaptive Business Operating System",
        description=(
            "A multi-agent framework for goal-driven business workflow automation. "
            "Translates high-level business goals into executable multi-department workflows."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # --- Routers ---
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
