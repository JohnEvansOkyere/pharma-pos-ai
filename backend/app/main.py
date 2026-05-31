"""
Main FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.app_mode import is_local_operational_write
from app.api import api_router
from app.services.scheduler import scheduler

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — migrations are run by render_start.sh before uvicorn launches.
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    scheduler.start()

    yield

    # Shutdown
    logger.info("Shutting down application")
    scheduler.stop()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local-first pharmaceutical POS system for pharmacy installations",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)


@app.middleware("http")
async def cloud_reporting_write_guard(request: Request, call_next):
    """Prevent cloud deployments from acting as a second local POS database."""
    if is_local_operational_write(
        app_mode=settings.APP_MODE,
        method=request.method,
        path=request.url.path,
    ):
        return JSONResponse(
            status_code=403,
            content={
                "detail": (
                    "This deployment is running in cloud reporting mode. "
                    "Local POS, product, stock, sales, notification, and system writes "
                    "must be performed on the pharmacy installation."
                )
            },
        )
    return await call_next(request)

# Include API router
app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "mode": settings.APP_MODE,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint — verifies database connectivity."""
    from sqlalchemy import text
    from fastapi.responses import JSONResponse
    from app.db.base import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
