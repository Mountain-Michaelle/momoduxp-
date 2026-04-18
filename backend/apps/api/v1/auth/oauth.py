"""
Google OAuth 2.0 configuration using authlib.
Production-ready with proper state token security and token rotation.
"""

import secrets
import logging
from typing import Optional
from authlib.integrations.requests_client import OAuth2Session
from urllib.parse import urlencode
from apps.api.config import api_settings

logger = logging.getLogger(__name__)


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)


class GoogleOAuthClient:
    def __init__(self, client_id: str = None, client_secret: str = None):
        oauth_config = api_settings.google_oauth_config
        self.client_id = client_id or oauth_config["client_id"]
        self.client_secret = client_secret or oauth_config["client_secret"]
        self.redirect_uri = oauth_config["redirect_uri"]
        self.scopes = oauth_config["scope"]
        self.authorize_url = oauth_config["authorize_url"]
        self.token_url = oauth_config["access_token_url"]
        self.userinfo_url = oauth_config["userinfo_url"]

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }

        query = urlencode(params)
        return f"{self.authorize_url}?{query}"

    def exchange_code_for_tokens(self, code: str) -> dict:
        client = OAuth2Session(
            self.client_id,
            self.client_secret,
            redirect_uri=self.redirect_uri,
        )

        token = client.fetch_token(
            self.token_url,
            code=code,
            grant_type="authorization_code",
        )

        return {
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token"),
            "id_token": token.get("id_token"),
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at"),
            "scope": token.get("scope"),
        }

    def refresh_access_token(self, refresh_token: str) -> dict:
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
            "refresh_token": token.get("refresh_token", refresh_token),
            "id_token": token.get("id_token"),
            "token_type": token.get("token_type", "Bearer"),
            "expires_at": token.get("expires_at"),
            "scope": token.get("scope"),
        }

    def _normalize_userinfo(self, data: dict) -> dict:
        email = data.get("email") or data.get("preferred_username")
        if not email and isinstance(data.get("emails"), list) and data["emails"]:
            first = data["emails"][0]
            if isinstance(first, dict):
                email = first.get("value")

        return {
            "google_id": data.get("sub") or data.get("id"),
            "email": email,
            "email_verified": data.get("email_verified", False),
            "name": data.get("name"),
            "given_name": data.get("given_name"),
            "family_name": data.get("family_name"),
            "picture": data.get("picture"),
            "locale": data.get("locale"),
        }

    def get_user_info(self, access_token: str) -> dict:
        import requests

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        endpoints = [
            self.userinfo_url,
            "https://openidconnect.googleapis.com/v1/userinfo",
            "https://www.googleapis.com/oauth2/v2/userinfo",
        ]

        last_non_empty = {}
        last_error = None

        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                normalized = self._normalize_userinfo(data)

                logger.info(
                    "Google userinfo endpoint responded: endpoint=%s google_id=%s email_present=%s",
                    endpoint,
                    normalized.get("google_id"),
                    bool(normalized.get("email")),
                )

                if any(normalized.values()):
                    last_non_empty = normalized

                if normalized.get("email"):
                    return normalized
            except Exception as exc:
                last_error = exc
                logger.warning("Google userinfo request failed for %s: %s", endpoint, exc)

        if last_non_empty:
            return last_non_empty

        if last_error:
            raise last_error

        return {}

    def get_id_token_info(self, id_token: str) -> dict:
        import requests

        response = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()
        return self._normalize_userinfo(data)


google_oauth_client: Optional[GoogleOAuthClient] = None


def get_google_oauth_client() -> GoogleOAuthClient:
    global google_oauth_client
    if google_oauth_client is None:
        google_oauth_client = GoogleOAuthClient()
    return google_oauth_client
