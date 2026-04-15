"""
Google OAuth 2.0 configuration using authlib.
Production-ready with proper state token security and token rotation.
"""

import secrets
import logging
from typing import Optional
from authlib.integrations.requests_client import OAuth2Session
from authlib.oauth2.auth import TokenCredential
from authlib.common.security import generate_token

from apps.api.config import api_settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# OAuth State Management (CSRF Protection)
# ─────────────────────────────────────────────────────────────


def generate_oauth_state() -> str:
    """Generate cryptographically secure state token."""
    return secrets.token_urlsafe(32)


# ─────────────────────────────────────────────────────────────
# Google OAuth Client Factory
# ─────────────────────────────────────────────────────────────


class GoogleOAuthClient:
    """
    Google OAuth 2.0 client with authlib.
    Handles authorization code exchange and token refresh.
    """
    
    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or api_settings.GOOGLE_CLIENT_ID
        self.client_secret = client_secret or api_settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = api_settings.GOOGLE_REDIRECT_URI
        self.scopes = api_settings.GOOGLE_SCOPES
        self.authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    
    def get_authorization_url(self, state: str) -> str:
        """Generate Google OAuth authorization URL with required parameters."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Force consent to get refresh token
        }
        
        # Build URL with query params
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.authorize_url}?{query}"
    
    def exchange_code_for_tokens(self, code: str) -> dict:
        """
        Exchange authorization code for access and refresh tokens.
        Returns dict with access_token, refresh_token, expires_at, id_token.
        """
        client = OAuth2Session(
            self.client_id,
            self.client_secret,
            redirect_uri=self.redirect_uri,
        )
        
        # Fetch token from Google
        token = client.fetch_token(
            self.token_url,
            code=code,
            grant_type="authorization_code",
        )
        
        # Extract and normalize token data
        return {
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "id_token": token.get("id_token"),
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at"),
            "scope": token.get("scope"),
        }
    
    def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Refresh access token using refresh token.
        Used for silent re-authentication without user interaction.
        """
        client = OAuth2Session(
            self.client_id,
            self.client_secret,
        )
        
        token = client.refresh_token(
            self.token_url,
            refresh_token=refresh_token,
        )
        
        return {
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token", refresh_token),  # Keep old if not returned
            "id_token": token.get("id_token"),
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at"),
            "scope": token.get("scope"),
        }
    
    def get_user_info(self, access_token: str) -> dict:
        """
        Fetch user profile from Google API.
        Uses access_token to get userinfo endpoint.
        """
        import requests
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        
        response = requests.get(self.userinfo_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Normalize to our user model format
        return {
            "google_id": data.get("sub"),
            "email": data.get("email"),
            "email_verified": data.get("email_verified", False),
            "name": data.get("name"),
            "given_name": data.get("given_name"),
            "family_name": data.get("family_name"),
            "picture": data.get("picture"),
            "locale": data.get("locale"),
        }


# ─────────────────────────────────────────────────────────────
# Singleton Instance
# ─────────────────────────────────────────────────────────────

google_oauth_client: Optional[GoogleOAuthClient] = None


def get_google_oauth_client() -> GoogleOAuthClient:
    """Get or create Google OAuth client singleton."""
    global google_oauth_client
    if google_oauth_client is None:
        google_oauth_client = GoogleOAuthClient()
    return google_oauth_client