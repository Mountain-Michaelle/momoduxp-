"""
FastAPI application-level dependencies.
Rate limiting and re-exports of auth dependencies.

Auth/JWT logic lives in api/v1/auth/dependencies.py.
"""

from datetime import datetime, timezone

from shared.exceptions import RateLimitException

# Re-export auth dependencies so existing imports keep working
from apps.api.v1.auth.dependencies import (  # noqa: F401
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_current_user,
    get_current_active_user,
    get_current_superuser,
    security,
)


# -------------------------------------------------------
# Rate limiting (in-memory; use Redis/slowapi in production)
# -------------------------------------------------------

class AsyncRateLimiter:
    """
    Simple in-memory async rate limiter.

    Note: For production, use Redis-based rate limiting (slowapi+redis).
    """

    def __init__(self, requests: int = 60, seconds: int = 60):
        self.requests = requests
        self.seconds = seconds
        self.clients: dict[str, list[datetime]] = {}

    async def check_rate_limit(self, client_id: str) -> bool:
        now = datetime.now(timezone.utc)

        if client_id not in self.clients:
            self.clients[client_id] = []

        self.clients[client_id] = [
            req_time for req_time in self.clients[client_id]
            if (now - req_time).total_seconds() < self.seconds
        ]

        if len(self.clients[client_id]) >= self.requests:
            return False

        self.clients[client_id].append(now)
        return True

    async def get_remaining(self, client_id: str) -> int:
        now = datetime.now(timezone.utc)

        if client_id not in self.clients:
            return self.requests

        self.clients[client_id] = [
            req_time for req_time in self.clients[client_id]
            if (now - req_time).total_seconds() < self.seconds
        ]

        return max(0, self.requests - len(self.clients[client_id]))


# Global rate limiter instances
rate_limiter = AsyncRateLimiter(requests=60, seconds=60)
ai_rate_limiter = AsyncRateLimiter(requests=10, seconds=60)  # Stricter for AI endpoints


async def rate_limit_dependency(
    client_id: str,
    limiter: AsyncRateLimiter = rate_limiter,
) -> None:
    """
    Rate limiting dependency for endpoints.

    Raises:
        RateLimitException: If rate limit exceeded
    """
    if not await limiter.check_rate_limit(client_id):
        raise RateLimitException(detail="Rate limit exceeded. Please try again later.")
