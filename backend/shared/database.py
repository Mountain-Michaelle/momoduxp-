"""
Shared database configuration — FastAPI (async) + Celery (sync).

Design rules:
  - Async engine  → FastAPI / ASGI layer only  (asyncpg)
  - Sync  engine  → Celery workers only        (psycopg2)
  - Both engines are lazy: created on first use, never at import time.
    This means importing this module in a Celery worker will NOT
    instantiate the asyncpg engine, eliminating the "Event loop is
    closed" crash on connection teardown.
  - Pool sizes are env-configurable so they can be tuned per deployment
    without code changes. Keep them small; let PgBouncer do the pooling.
"""

import asyncio
import logging
import os
from contextlib import contextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from apps.api.config import api_settings

logger = logging.getLogger(__name__)


# ── URL helpers ───────────────────────────────────────────────────────────────


def _to_asyncpg_url(url: str) -> str:
    """Normalise any postgres:// variant to postgresql+asyncpg://."""
    for prefix, replacement in (
        ("postgresql+asyncpg://", "postgresql+asyncpg://"),
        ("postgresql://", "postgresql+asyncpg://"),
        ("postgres://", "postgresql+asyncpg://"),
    ):
        if url.startswith(prefix):
            return url.replace(prefix, replacement, 1)
    return url


def _to_psycopg2_url(url: str) -> str:
    """Normalise any postgres:// variant to postgresql+psycopg2://."""
    for prefix, replacement in (
        ("postgresql+asyncpg://", "postgresql+psycopg2://"),
        ("postgresql+psycopg2://", "postgresql+psycopg2://"),
        ("postgresql://", "postgresql+psycopg2://"),
        ("postgres://", "postgresql+psycopg2://"),
    ):
        if url.startswith(prefix):
            return url.replace(prefix, replacement, 1)
    return url


def _async_url() -> str:
    return os.getenv("ASYNC_DATABASE_URL") or _to_asyncpg_url(api_settings.DATABASE_URL)


def _sync_url() -> str:
    return os.getenv("SYNC_DATABASE_URL") or _to_psycopg2_url(api_settings.DATABASE_URL)


# ── Pool configuration ────────────────────────────────────────────────────────


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


ASYNC_POOL_SIZE = _int_env("ASYNC_POOL_SIZE", 5)
ASYNC_MAX_OVERFLOW = _int_env("ASYNC_MAX_OVERFLOW", 10)
SYNC_POOL_SIZE = _int_env("SYNC_POOL_SIZE", 3)
SYNC_MAX_OVERFLOW = _int_env("SYNC_MAX_OVERFLOW", 5)
POOL_TIMEOUT = _int_env("DB_POOL_TIMEOUT", 30)


# ── Lazy engine singletons ────────────────────────────────────────────────────
# Engines are module-level singletons but are NOT created at import time.
# Call get_async_engine() / get_sync_engine() to obtain (or create) them.
# This guarantees that importing this module inside a Celery worker does not
# spin up an asyncpg connection pool, which would crash when asyncio.run()
# later closes the event loop underneath it.

_async_engine = None
_sync_engine = None
_async_session_maker: async_sessionmaker | None = None
_sync_session_maker: sessionmaker | None = None


def get_async_engine():
    global _async_engine, _async_session_maker
    if _async_engine is None:
        _async_engine = create_async_engine(
            _async_url(),
            echo=api_settings.API_DEBUG,
            pool_pre_ping=True,
            pool_size=ASYNC_POOL_SIZE,
            max_overflow=ASYNC_MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
        )
        _async_session_maker = async_sessionmaker(
            _async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.debug("Async DB engine created url=%s", _async_url())
    return _async_engine


def get_sync_engine():
    global _sync_engine, _sync_session_maker
    if _sync_engine is None:
        _sync_engine = create_engine(
            _sync_url(),
            echo=api_settings.API_DEBUG,
            pool_pre_ping=True,
            pool_size=SYNC_POOL_SIZE,
            max_overflow=SYNC_MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
        )
        _sync_session_maker = sessionmaker(
            bind=_sync_engine,
            expire_on_commit=False,
        )
        logger.debug("Sync DB engine created url=%s", _sync_url())
    return _sync_engine


# Convenience accessors used by callers that need the session maker directly.
def get_async_session_maker() -> async_sessionmaker:
    get_async_engine()
    return _async_session_maker


def get_sync_session_maker() -> sessionmaker:
    get_sync_engine()
    return _sync_session_maker


# ── Public session factories ──────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a managed async session."""
    async with get_async_session_maker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@contextmanager
def get_sync_session() -> Session:
    """
    Celery / sync context manager — always commit, rollback, and close.

    Usage:
        with get_sync_session() as db:
            db.execute(...)
    """
    session: Session = get_sync_session_maker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Alias kept for backwards compat with existing async task code.
# def get_async_session_maker_cached() -> async_sessionmaker:
#     return get_async_session_maker()


# async_session_maker = get_async_session_maker_cached()


# ── ORM base ─────────────────────────────────────────────────────────────────

Base = declarative_base()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

_db_init_lock = asyncio.Lock()
_db_initialized = False


async def init_db() -> None:
    """
    Initialise DB resources on application startup.

    Protected by asyncio.Lock so concurrent ASGI workers cannot
    double-initialise.  Schema creation only runs in DEBUG mode.
    """
    global _db_initialized
    async with _db_init_lock:
        if _db_initialized:
            return

        if api_settings.API_DEBUG:
            async with get_async_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables ensured (DEV ONLY — never run in production)")
        else:
            logger.info("Schema creation skipped (production mode)")

        _db_initialized = True


async def close_db() -> None:
    """Dispose both engines on application shutdown."""
    if _async_engine is not None:
        await _async_engine.dispose()
        logger.info("Async DB engine disposed")
    if _sync_engine is not None:
        _sync_engine.dispose()
        logger.info("Sync DB engine disposed")


# ── Health checks ─────────────────────────────────────────────────────────────


async def check_async_db() -> bool:
    """Liveness probe for the async (FastAPI) engine."""
    try:
        async with get_async_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Async DB health check failed")
        return False


def check_sync_db() -> bool:
    """Liveness probe for the sync (Celery) engine."""
    try:
        with get_sync_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Sync DB health check failed")
        return False


async def check_db_connection() -> bool:
    """Combined health check — both engines must be reachable."""
    async_ok = await check_async_db()
    sync_ok = check_sync_db()
    return async_ok and sync_ok
