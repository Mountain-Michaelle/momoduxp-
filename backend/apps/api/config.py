"""
FastAPI configuration settings.
Uses pydantic-settings for environment variable management.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    """FastAPI application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application settings (non-sensitive)
    APP_NAME: str = "Momodu API"
    APP_VERSION: str = "1.0.0"
    API_DEBUG: bool = False

    # CORS settings (non-sensitive defaults)
    CORS_ORIGINS: str = ""
    CORS_ALLOW_CREDENTIALS: bool = True

    # Security settings - MUST be set from environment
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = ""
    JWT_AUDIENCE: str = ""

    # Google OAuth settings - MUST be set from environment
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # OAuth scopes (non-sensitive, can keep defaults)
    GOOGLE_SCOPES: str = "openid email profile https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"

    # Encryption key - MUST be set from environment
    ENCRYPTION_KEY: str = ""

    # Database settings - MUST be set from environment
    DATABASE_URL: str = ""

    # External services - MUST be set from environment
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = ""
    LINKEDIN_BASE_URL: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = ""
    TELEGRAM_BASE_URL: str = ""
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_BOT_USERNAME: str = ""
    PUBLIC_API_BASE_URL: Optional[str] = None

    # Redis settings - MUST be set from environment
    REDIS_URL: str = ""

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000", "http://localhost:8000"]
        if isinstance(self.CORS_ORIGINS, str):
            import ast

            try:
                return ast.literal_eval(self.CORS_ORIGINS)
            except:
                return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

    @property
    def google_oauth_scopes(self) -> List[str]:
        """Parse scopes from string."""
        if isinstance(self.GOOGLE_SCOPES, list):
            return self.GOOGLE_SCOPES
        return self.GOOGLE_SCOPES.split() if self.GOOGLE_SCOPES else []

    @property
    def google_oauth_config(self) -> dict:
        """Google OAuth configuration - all sensitive values from environment."""
        return {
            "client_id": self.GOOGLE_CLIENT_ID,
            "client_secret": self.GOOGLE_CLIENT_SECRET,
            "redirect_uri": self.GOOGLE_REDIRECT_URI,
            "scope": self.google_oauth_scopes,
            "issuer": os.getenv("GOOGLE_ISSUER", "https://accounts.google.com"),
            "access_token_url": os.getenv(
                "GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token"
            ),
            "userinfo_url": os.getenv(
                "GOOGLE_USERINFO_URL", "https://www.googleapis.com/oauth2/v3/userinfo"
            ),
            "authorize_url": os.getenv(
                "GOOGLE_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth"
            ),
        }

# Global settings instance
api_settings = APISettings()
