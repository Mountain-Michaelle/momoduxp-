"""
Authentication dependencies for FastAPI.
Centralised JWT auth logic: token creation, decoding, and user resolution.
"""

from typing import Optional
from datetime import timedelta, timezone, datetime
from jose import JWTError, jwt
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.exceptions import AuthenticationException
from shared.models import User
from apps.api.v1.auth.jwt import decode_token, ACCESS
from apps.api.v1.repositories.user import get_user_by_id
from apps.api.config import api_settings


security = HTTPBearer(auto_error=False)


# -------------------------------------------------------
# Token creation helpers (canonical implementations)
# -------------------------------------------------------

def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None,
) -> str:
    to_encode = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=api_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        ),
        "iss": api_settings.JWT_ISSUER,
        "aud": api_settings.JWT_AUDIENCE,
    }
    if additional_claims:
        to_encode.update(additional_claims)
    return jwt.encode(to_encode, api_settings.SECRET_KEY, algorithm=api_settings.ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    to_encode = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=api_settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "iss": api_settings.JWT_ISSUER,
        "aud": api_settings.JWT_AUDIENCE,
    }
    return jwt.encode(to_encode, api_settings.SECRET_KEY, algorithm=api_settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return decode_token(token)
    except JWTError:
        return None


# -------------------------------------------------------
# FastAPI dependency functions
# -------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise AuthenticationException(message="Missing credentials")

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise AuthenticationException(message="Invalid or expired token")

    if payload.get("type") != ACCESS:
        raise AuthenticationException(message="Invalid token type")

    user = await get_user_by_id(db, payload["sub"])
    if not user:
        raise AuthenticationException(message="User not found")

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise AuthenticationException(message="Inactive account")
    return user


async def get_current_superuser(
    user: User = Depends(get_current_active_user),
) -> User:
    if not user.is_superuser:
        raise AuthenticationException(message="Insufficient privileges")
    return user
