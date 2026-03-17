"""
Shared database configuration for FastAPI and Django.

- Async SQLAlchemy for FastAPI
- Django ORM remains isolated
- Pool-safe under multi-worker ASGI
- Production-safe defaults
"""

import os
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from api.config import api_settings

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Database URL handling
# ------------------------------------------------------------------------------

def get_async_database_url() -> str:
    async_url = os.getenv("ASYNC_DATABASE_URL")
    if async_url:
        return async_url

    db_url = api_settings.DATABASE_URL

    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql+asyncpg://", 1)

    return db_url


DATABASE_URL = get_async_database_url()


# ------------------------------------------------------------------------------
# Engine & session
# ------------------------------------------------------------------------------

CPU_COUNT = os.cpu_count() or 2

engine = create_async_engine(
    DATABASE_URL,
    echo=api_settings.DEBUG,
    pool_pre_ping=True,
    pool_size=CPU_COUNT * 2,
    max_overflow=CPU_COUNT * 4,
    pool_timeout=30,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


# ------------------------------------------------------------------------------
# Dependency
# ------------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ------------------------------------------------------------------------------
# Lifecycle helpers
# ------------------------------------------------------------------------------

_db_initialized = False


async def init_db() -> None:
    """
    Initialize DB resources.

    WARNING:
    - Never auto-create tables in production
    """
    global _db_initialized
    if _db_initialized:
        return

    if api_settings.DEBUG:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured (DEV ONLY)")
    else:
        logger.info("Skipping schema creation (PRODUCTION)")

    _db_initialized = True


async def close_db() -> None:
    await engine.dispose()
    logger.info("Database engine disposed")


# ------------------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------------------

async def check_db_connection() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False
