"""FastAPI application factory and executable entrypoint."""

import uvicorn
from fastapi import FastAPI

from veridash_api.routes.health import router as health_router


def create_app() -> FastAPI:
    """Create an API instance without connecting to external services."""
    app = FastAPI(title="VeriDash API", version="0.1.0")
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()


def run() -> None:
    """Run the development-compatible ASGI server entrypoint."""
    uvicorn.run("veridash_api.main:app", host="127.0.0.1", port=8000)
