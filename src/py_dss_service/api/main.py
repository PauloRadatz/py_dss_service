"""
FastAPI application entry point.

Run with: python -m py_dss_service.api.main
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from py_dss_service.api.routers import health_router, jobs_router, sessions_router
from py_dss_service.logging import setup_logging
from py_dss_service.sessions.manager import get_session_manager
from py_dss_service.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup: Start session cleanup task
    session_manager = get_session_manager()
    await session_manager.start_cleanup_task()
    
    yield  # App is running
    
    # Shutdown: Stop session cleanup task
    await session_manager.stop_cleanup_task()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Ensure data directories exist
    settings.ensure_directories()

    app = FastAPI(
        title="py-dss-service",
        description="OpenDSS simulation service with sessions (interactive) and jobs (batch) APIs",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(sessions_router)  # Sessions API (interactive)
    app.include_router(jobs_router)      # Jobs API (batch)

    return app


# Create app instance for ASGI servers
app = create_app()


def main() -> None:
    """Run the API server."""
    settings = get_settings()
    setup_logging(level=settings.log_level)

    print(f"Starting py-dss-service API on {settings.api_host}:{settings.api_port}")
    print(f"Data directory: {settings.pydss_data_dir.absolute()}")
    print(f"API docs: http://{settings.api_host}:{settings.api_port}/docs")

    uvicorn.run(
        "py_dss_service.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()

