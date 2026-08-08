"""FastAPI application factory and executable entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from veridash_analysis import AnalysisRegistry
from veridash_analysis.modules import production_manifests
from veridash_storage import FilesystemBlobStore, UploadBlobStore

from veridash_api.config import Settings
from veridash_api.errors import install_error_handlers
from veridash_api.models import PROBLEM_RESPONSE
from veridash_api.routes.analyses import router as analyses_router
from veridash_api.routes.auth import router as auth_router
from veridash_api.routes.health import router as health_router
from veridash_api.routes.media import router as media_router
from veridash_api.routes.projects import router as projects_router


def create_app(
    *,
    settings: Settings | None = None,
    database_engine: AsyncEngine | None = None,
    blob_store: UploadBlobStore | None = None,
    analysis_registry: AnalysisRegistry | None = None,
) -> FastAPI:
    """Create an API instance; external connections begin only in ASGI lifespan."""
    resolved_settings = settings or Settings()
    resolved_analysis_registry = analysis_registry or AnalysisRegistry(production_manifests())

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        engine = database_engine or create_async_engine(
            resolved_settings.database_url,
            pool_pre_ping=True,
        )
        application.state.database_engine = engine
        application.state.blob_store = blob_store or FilesystemBlobStore(
            resolved_settings.data_root
        )
        application.state.analysis_registry = resolved_analysis_registry
        try:
            yield
        finally:
            if database_engine is None:
                await engine.dispose()

    app = FastAPI(
        title="VeriDash API",
        version="0.1.0",
        lifespan=lifespan,
        responses={500: {**PROBLEM_RESPONSE, "description": "Internal server error"}},
    )
    app.state.settings = resolved_settings
    app.state.analysis_registry = resolved_analysis_registry
    if database_engine is not None:
        app.state.database_engine = database_engine
    if blob_store is not None:
        app.state.blob_store = blob_store
    install_error_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")
    app.include_router(media_router, prefix="/api")
    app.include_router(analyses_router, prefix="/api")
    return app


app = create_app()


def run() -> None:
    """Run the development-compatible ASGI server entrypoint."""
    uvicorn.run("veridash_api.main:app", host="127.0.0.1", port=8000)
