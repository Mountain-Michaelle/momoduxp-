"""
OAuth FastAPI Dependencies.
Provides OAuth-related dependency injection for routes.
"""

import logging
import json
from typing import Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis

from shared.database import get_db
from shared.models.users import User
from apps.api.v1.auth.dependencies import get_current_active_user
from apps.api.config import api_settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Redis Client Setup
# ─────────────────────────────────────────────────────────────

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            api_settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


# ─────────────────────────────────────────────────────────────
# OAuth State Management Dependencies
# ─────────────────────────────────────────────────────────────


class OAuthStateManager:
    """
    Manages OAuth state tokens for CSRF protection using Redis.
    Production-ready with TTL-based expiration and Redis storage.
    """

    STATE_PREFIX = "oauth:state:"
    STATE_TTL = 600  # 10 minutes

    @classmethod
    def store_state(
        cls, state: str, redirect_url: Optional[str] = None, expires_in: int = None
    ):
        """
        Store state token in Redis with TTL expiration.

        Args:
            state: The OAuth state token
            redirect_url: Optional URL to redirect after OAuth flow
            expires_in: TTL in seconds (default: 600 = 10 minutes)
        """
        r = get_redis_client()
        ttl = expires_in or cls.STATE_TTL

        data = {
            "redirect_url": redirect_url or "",
        }

        r.setex(
            f"{cls.STATE_PREFIX}{state}",
            ttl,
            json.dumps(data),
        )
        logger.debug("Stored OAuth state in Redis: %s (TTL: %ds)", state[:16], ttl)

    @classmethod
    def validate_state(cls, state: str) -> bool:
        """
        Validate state token from Redis.
        Removes state after validation to prevent replay attacks.

        Returns:
            True if valid, False otherwise
        """
        r = get_redis_client()
        key = f"{cls.STATE_PREFIX}{state}"

        # Get and delete atomically using GETDEL (Redis 7+)
        try:
            # Try GETDEL first (Redis 7+)
            stored_data = r.getdel(key)
        except Exception:
            # Fallback for older Redis
            stored_data = r.get(key)
            if stored_data:
                r.delete(key)

        if not stored_data:
            logger.warning("OAuth state not found in Redis: %s", state[:16])
            return False

        logger.debug("OAuth state validated from Redis: %s", state[:16])
        return True

    @classmethod
    def get_redirect_url(cls, state: str) -> Optional[str]:
        """Get stored redirect URL for state from Redis."""
        r = get_redis_client()
        key = f"{cls.STATE_PREFIX}{state}"

        stored_data = r.get(key)
        if stored_data:
            data = json.loads(stored_data)
            return data.get("redirect_url") or None
        return None

    @classmethod
    def delete_state(cls, state: str) -> bool:
        """Delete state from Redis (logout/revoke)."""
        r = get_redis_client()
        key = f"{cls.STATE_PREFIX}{state}"
        deleted = r.delete(key)
        return deleted > 0


# ─────────────────────────────────────────────────────────────
# Dependency Functions
# ─────────────────────────────────────────────────────────────


async def get_oauth_state_manager() -> OAuthStateManager:
    """Dependency to get OAuth state manager."""
    return OAuthStateManager()


# ─────────────────────────────────────────────────────────────
# OAuth Account Dependencies
# ─────────────────────────────────────────────────────────────


async def get_oauth_user_accounts(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    """
    Get all OAuth accounts linked to the current user.
    Use this to let users see their connected OAuth providers.
    """
    from apps.api.v1.repositories.oauth_repository import get_user_oauth_accounts

    accounts = await get_user_oauth_accounts(db, str(user.id))
    return accounts


async def require_oauth_provider(
    provider: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> bool:
    """
    Verify that user has linked the specified OAuth provider.
    Use for route protection that requires specific OAuth connection.

    Example:
        @router.get("/profile")
        async def get_profile(
            _: bool = Depends(require_oauth_provider("google"))
        ):
            ...
    """
    from apps.api.v1.repositories.oauth_repository import (
        get_oauth_account_by_provider_and_user,
    )

    account = await get_oauth_account_by_provider_and_user(db, str(user.id), provider)

    if not account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User has not linked {provider} account",
        )

    return True
