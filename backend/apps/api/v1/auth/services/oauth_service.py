"""
OAuth Service Layer - Business logic for OAuth authentication.
Handles the complete OAuth flow: authorization, token exchange, user creation/linking.
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.v1.auth.oauth import (
    get_google_oauth_client,
    generate_oauth_state,
    GoogleOAuthClient,
)
from apps.api.v1.auth.dependencies import create_access_token, create_refresh_token
from apps.api.v1.repositories.oauth_repository import (
    OAuthProvider,
    create_oauth_account,
    get_oauth_account_by_provider_user_id,
)
from apps.api.v1.repositories.user import get_user_by_email, create_user
from shared.models.users import User
from apps.api.config import api_settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# OAuth Service Result Types
# ─────────────────────────────────────────────────────────────


class OAuthTokens:
    """OAuth tokens returned after successful authentication."""
    
    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        user_id: str,
        email: str,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.user_id = user_id
        self.email = email


class OAuthAuthorizationURL:
    """OAuth authorization URL with state token."""
    
    def __init__(self, url: str, state: str):
        self.url = url
        self.state = state


# ─────────────────────────────────────────────────────────────
# OAuth Service Functions
# ─────────────────────────────────────────────────────────────


async def get_google_authorization_url() -> OAuthAuthorizationURL:
    """
    Generate Google OAuth authorization URL with secure state token.
    Returns URL and state for CSRF validation on callback.
    """
    state = generate_oauth_state()
    client = get_google_oauth_client()
    url = client.get_authorization_url(state)
    
    logger.info("Generated Google OAuth URL with state token")
    
    return OAuthAuthorizationURL(url=url, state=state)


async def handle_google_callback(
    db: AsyncSession,
    code: str,
    state: str,
    expected_state: Optional[str] = None,
) -> OAuthTokens:
    """
    Handle Google OAuth callback.
    
    1. Validate state token (CSRF protection)
    2. Exchange authorization code for tokens
    3. Get user info from Google
    4. Find or create user
    5. Create OAuth account linking
    6. Generate JWT tokens
    
    Args:
        db: Database session
        code: Authorization code from Google
        state: State token from Google callback
        expected_state: State token we generated (for CSRF validation)
    
    Returns:
        OAuthTokens with JWT access and refresh tokens
    """
    # Validate state token (CSRF protection)
    if expected_state and state != expected_state:
        logger.error("OAuth state mismatch: expected=%s got=%s", expected_state, state)
        raise ValueError("Invalid OAuth state - possible CSRF attack")
    
    # Exchange code for tokens
    client = get_google_oauth_client()
    
    try:
        token_data = client.exchange_code_for_tokens(code)
    except Exception as e:
        logger.error("Failed to exchange OAuth code for tokens: %s", e)
        raise ValueError(f"Failed to exchange authorization code: {e}")
    
    # Get user info from Google
    try:
        user_info = client.get_user_info(token_data["access_token"])
    except Exception as e:
        logger.error("Failed to get user info from Google: %s", e)
        raise ValueError(f"Failed to get user info: {e}")
    
    # Validate email
    if not user_info.get("email"):
        raise ValueError("Google account must have an email address")
    
    # Find or create user
    user = await _find_or_create_oauth_user(
        db,
        provider=OAuthProvider.GOOGLE,
        provider_user_id=user_info["google_id"],
        email=user_info["email"],
        name=user_info.get("name"),
        picture=user_info.get("picture"),
    )
    
    # Create OAuth account with tokens
    expires_at = None
    if token_data.get("expires_at"):
        expires_at = datetime.fromtimestamp(token_data["expires_at"])
    
    await create_oauth_account(
        db=db,
        user_id=str(user.id),
        provider=OAuthProvider.GOOGLE,
        provider_user_id=user_info["google_id"],
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        id_token=token_data.get("id_token"),
        token_expires_at=expires_at,
        scope=token_data.get("scope", ""),
    )
    
    # Generate JWT tokens
    access_token = create_access_token(
        user_id=str(user.id),
        additional_claims={"email": user.email, "provider": "google"},
    )
    refresh_token = create_refresh_token(user_id=str(user.id))
    
    # Calculate expires in seconds
    expires_in = api_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    logger.info(
        "OAuth login successful: user_id=%s email=%s provider=%s",
        user.id,
        user.email,
        OAuthProvider.GOOGLE,
    )
    
    return OAuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user_id=str(user.id),
        email=user.email,
    )


async def refresh_oauth_token(
    db: AsyncSession,
    provider: str,
    refresh_token: str,
) -> dict:
    """
    Refresh OAuth access token using refresh token.
    Used for silent re-authentication without user interaction.
    """
    client = get_google_oauth_client()
    
    try:
        new_token_data = client.refresh_access_token(refresh_token)
    except Exception as e:
        logger.error("Failed to refresh OAuth token: %s", e)
        raise ValueError(f"Failed to refresh token: {e}")
    
    return new_token_data


# ─────────────────────────────────────────────────────────────
# User Resolution (Internal)
# ─────────────────────────────────────────────────────────────


async def _find_or_create_oauth_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    name: Optional[str] = None,
    picture: Optional[str] = None,
) -> User:
    """
    Find existing user by OAuth account or create new user.
    This implements the OAuth identity resolution logic:
    1. Check if OAuth account exists (user already linked)
    2. Check if user with this email exists (link to OAuth)
    3. Create new user with OAuth info
    """
    # Step 1: Check if OAuth account already exists
    oauth_account = await get_oauth_account_by_provider_user_id(
        db, provider, provider_user_id
    )
    
    if oauth_account:
        # User already has this OAuth linked - fetch the user
        user = await db.get(User, oauth_account.user_id)
        if user:
            logger.info(
                "Found existing user from OAuth: user_id=%s provider=%s",
                user.id,
                provider,
            )
            return user
        
        logger.error(
            "OAuth account exists but user not found: user_id=%s",
            oauth_account.user_id,
        )
        # Continue to create new user
    
    # Step 2: Check if user with this email exists
    existing_user = await get_user_by_email(db, email)
    if existing_user:
        logger.info(
            "Linking existing user to OAuth: user_id=%s email=%s provider=%s",
            existing_user.id,
            email,
            provider,
        )
        # OAuth account will be created by caller
        return existing_user
    
    # Step 3: Create new user
    logger.info(
        "Creating new user from OAuth: email=%s provider=%s name=%s",
        email,
        provider,
        name,
    )
    
    # Generate username from email or name
    username = email.split("@")[0] if email else (name or "user").lower().replace(" ", "_")
    
    # Handle potential duplicate username
    base_username = username
    counter = 1
    while await _username_exists(db, username):
        username = f"{base_username}{counter}"
        counter += 1
    
    # Create user
    new_user = await create_user(
        db=db,
        username=username,
        email=email,
        first_name=name.split()[0] if name else "",
        last_name=" ".join(name.split()[1:]) if name and " " in name else "",
        password=None,  # OAuth users don't have password
    )
    
    logger.info(
        "Created new OAuth user: user_id=%s email=%s username=%s",
        new_user.id,
        new_user.email,
        new_user.username,
    )
    
    return new_user


async def _username_exists(db: AsyncSession, username: str) -> bool:
    """Check if username already exists."""
    from sqlalchemy import select
    from shared.models.users import User
    
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None