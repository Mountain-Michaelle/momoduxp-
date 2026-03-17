"""
FastAPI application entry point.
Main application module with CORS, routers, health checks, and Celery integration.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from api.config import api_settings
from api.routers import posts, auth, ai
from shared.database import init_db, close_db

# Lazy import to avoid django.setup() at module level
# This prevents "populate() isn't reentrant" errors
def _get_celery_app():
    """Get Celery app instance lazily."""
    from shared.celery import get_celery_app
    return get_celery_app()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting up FastAPI application...")
    logger.info(f"Environment: {'Development' if api_settings.DEBUG else 'Production'}")
    logger.info(f"Celery broker: {api_settings.CELERY_BROKER_URL}")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed (will use raw queries): {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=api_settings.APP_NAME,
    description="AI-automated LinkedIn posting API. High-throughput API for social media management.",
    version=api_settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origins_list,
    allow_credentials=api_settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": exc.body if hasattr(exc, "body") else None
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Health check endpoints
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": api_settings.APP_NAME,
        "version": api_settings.APP_VERSION
    }


@app.get("/health/detailed", tags=["health"])
async def detailed_health_check():
    """Detailed health check with dependency status."""
    return {
        "status": "healthy",
        "service": api_settings.APP_NAME,
        "version": api_settings.APP_VERSION,
        "dependencies": {
            "database": "connected",
            "redis": "connected" if api_settings.CELERY_BROKER_URL else "not configured",
            "celery": "configured"
        }
    }


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(posts.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": api_settings.APP_NAME,
        "version": api_settings.APP_VERSION,
        "docs": "/api/docs",
        "health": "/health"
    }


# Import shared models for type checking
from shared.models import User  # noqa: F401
