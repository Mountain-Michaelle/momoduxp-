"""
OAuth Router - FastAPI endpoints for OAuth authentication.
Handles Google OAuth flow: authorization, callback, token refresh.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from shared.database import get_db
from apps.api.v1.auth.services.oauth_service import (
    get_google_authorization_url,
    handle_google_callback,
    OAuthAuthorizationURL,
    OAuthTokens,
)
from apps.api.v1.auth.deps.oauth_dependencies import OAuthStateManager
from apps.api.v1.auth.dependencies import get_current_active_user
from shared.models.users import User
from apps.api.v1.repositories.oauth_repository import get_user_oauth_accounts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])


# ─────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────


class OAuthUrlResponse(BaseModel):
    """Response with OAuth authorization URL."""
    url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Request with OAuth callback parameters."""
    code: str
    state: str


class OAuthTokenResponse(BaseModel):
    """Response with JWT tokens after OAuth login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str


class OAuthAccountResponse(BaseModel):
    """Response with OAuth account info."""
    id: str
    provider: str
    provider_user_id: str
    scope: str
    is_active: bool
    created_at: str


# ─────────────────────────────────────────────────────────────
# OAuth Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/google/url", response_model=OAuthUrlResponse)
async def get_google_oauth_url(
    redirect_url: str = Query(None, description="Optional URL to redirect after OAuth"),
    state_manager: OAuthStateManager = Depends(OAuthStateManager),
):
    """
    Get Google OAuth authorization URL.
    
    Returns a URL that the frontend should redirect the user to.
    The state parameter is included for CSRF protection.
    
    Example redirect URL:
        http://localhost:3000/oauth/callback
    """
    auth_url = await get_google_authorization_url()
    
    # Store state in Redis with optional redirect URL
    if redirect_url:
        state_manager.store_state(auth_url.state, redirect_url=redirect_url)
    else:
        state_manager.store_state(auth_url.state)
    
    return OAuthUrlResponse(
        url=auth_url.url,
        state=auth_url.state,
    )


@router.get("/google/callback", response_model=OAuthTokenResponse)
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State token for CSRF validation"),
    db: AsyncSession = Depends(get_db),
    state_manager: OAuthStateManager = Depends(OAuthStateManager),
):
    """
    Handle Google OAuth callback.
    
    This endpoint is called by Google after user authorizes the application.
    It exchanges the authorization code for tokens and creates/links user account.
    """
    # Validate state token (CSRF protection)
    if not state_manager.validate_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state token. Please try again.",
        )
    
    try:
        tokens = await handle_google_callback(
            db=db,
            code=code,
            state=state,
        )
    except ValueError as e:
        logger.error("OAuth callback failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Unexpected error in OAuth callback: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth authentication failed. Please try again.",
        )
    
    return OAuthTokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user_id=tokens.user_id,
        email=tokens.email,
    )


@router.get("/google/callback/error")
async def google_oauth_error(
    error: str = Query(..., description="Error from Google"),
    error_description: str = Query(None, description="Error description"),
):
    """
    Handle Google OAuth errors.
    
    This endpoint is called by Google when there's an error during OAuth.
    """
    logger.error("Google OAuth error: %s - %s", error, error_description)
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"OAuth error: {error_description or error}",
    )


# ─────────────────────────────────────────────────────────────
# User OAuth Account Management
# ─────────────────────────────────────────────────────────────


@router.get("/accounts", response_model=list[OAuthAccountResponse])
async def get_oauth_accounts(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all OAuth accounts linked to the current user.
    
    Returns list of connected OAuth providers (Google, GitHub, etc.)
    """
    accounts = await get_user_oauth_accounts(db, str(user.id))
    
    return [
        OAuthAccountResponse(
            id=str(acc.id),
            provider=acc.provider,
            provider_user_id=acc.provider_user_id,
            scope=acc.scope,
            is_active=acc.is_active,
            created_at=acc.created_at.isoformat() if acc.created_at else "",
        )
        for acc in accounts
    ]


@router.delete("/accounts/{account_id}")
async def unlink_oauth_account(
    account_id: str,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unlink an OAuth account from the current user.
    
    This disconnects the OAuth provider from the user's account.
    """
    import uuid
    from apps.api.v1.repositories.oauth_repository import delete_oauth_account
    
    try:
        account_uuid = uuid.UUID(account_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account ID",
        )
    
    # Verify ownership
    accounts = await get_user_oauth_accounts(db, str(user.id))
    account = next((acc for acc in accounts if str(acc.id) == account_id), None)
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth account not found",
        )
    
    await delete_oauth_account(db, account_uuid)
    
    return {"message": "OAuth account unlinked successfully"}


# ─────────────────────────────────────────────────────────────
# OAuth Token Refresh
# ─────────────────────────────────────────────────────────────


@router.post("/refresh")
async def refresh_oauth_token(
    refresh_token: str = Query(..., description="Refresh token from OAuth provider"),
    provider: str = Query("google", description="OAuth provider"),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh OAuth access token.
    
    Use this to get a new access token without re-authenticating.
    """
    from apps.api.v1.auth.services.oauth_service import refresh_oauth_token
    
    try:
        new_tokens = await refresh_oauth_token(db, provider, refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return {
        "access_token": new_tokens["access_token"],
        "refresh_token": new_tokens.get("refresh_token", refresh_token),
        "expires_at": new_tokens.get("expires_at"),
    }