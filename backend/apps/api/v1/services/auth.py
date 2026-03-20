# services/auth.py

from datetime import timedelta
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from shared.models import User
from shared.exceptions import (
    AuthenticationException,
    ConflictException,
)

from apps.api.v1.auth.jwt import create_token, ACCESS, REFRESH
from apps.api.config import api_settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=[
        "bcrypt",
        # Support users created through Django auth and migrate on next password change.
        "django_pbkdf2_sha256",
        "django_bcrypt_sha256",
    ],
    default="bcrypt",
    deprecated="auto",
)


# ------------------------
# Password handling
# ------------------------

def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise AuthenticationException(message="Invalid password format")
    return pwd_context.hash(password)

def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise AuthenticationException("Password too short")

    if not re.search(r"[A-Z]", password):
        raise AuthenticationException("Password must contain an uppercase letter")

    if not re.search(r"[a-z]", password):
        raise AuthenticationException("Password must contain a lowercase letter")

    if not re.search(r"[0-9]", password):
        raise AuthenticationException("Password must contain a number")



def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return pwd_context.verify(password, hashed.strip())
    except (UnknownHashError, ValueError, TypeError):
        logger.warning("Unsupported password hash format encountered during login")
        return False


# ------------------------
# Authentication
# ------------------------

async def authenticate_user(
    db: AsyncSession,
    identifier: str,
    password: str,
) -> User:
    """
    Authenticate a user by username or email.

    Raises:
        AuthenticationException
    """
    result = await db.execute(
        select(User).where(
            or_(
                User.username == identifier,
                User.email == identifier,
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password):
        raise AuthenticationException(message="Invalid credentials")

    if not user.is_active:
        raise AuthenticationException(message="Account is disabled")

    return user


# ------------------------
# Registration
# ------------------------

async def register_user(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    """
    Register a new user.

    Raises:
        ConflictException
    """
    async with db.begin():
        username = username.lower()
        email = email.lower()

        result = await db.execute(
            select(User.id).where(
                or_(
                    User.username == username,
                    User.email == email,
                )
            )
        )
        if result.first():
            raise ConflictException(message=f"A user with {username} already exists")
        validate_password_policy(password)
        user = User(
            username=username,
            email=email,
            password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )

        db.add(user)

    await db.refresh(user)

    return user


# ------------------------
# Token issuing
# ------------------------

def issue_tokens(user: User) -> dict:
    """
    Issue access and refresh tokens for a user.
    """
    access_token = create_token(
        subject=str(user.id),
        token_type=ACCESS,
        expires_delta=timedelta(
            minutes=api_settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    )

    refresh_token = create_token(
        subject=str(user.id),
        token_type=REFRESH,
        expires_delta=timedelta(
            days=api_settings.REFRESH_TOKEN_EXPIRE_DAYS
        ),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": str(user.id),
        "token_type": "bearer",
        "expires_in": api_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ------------------------
# Refresh flow
# ------------------------

def issue_access_token(user: User) -> dict:
    """
    Issue a new access token (used during refresh).
    """
    token = create_token(
        subject=str(user.id),
        token_type=ACCESS,
        expires_delta=timedelta(
            minutes=api_settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "expires_in": api_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
