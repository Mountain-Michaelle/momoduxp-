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
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application settings
    APP_NAME: str = "Momodu API"
    APP_VERSION: str = "1.0.0"
    API_DEBUG: bool = False

    # CORS settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True

    # Security settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # JWT settings
    JWT_ISSUER: str = "momodu-api"
    JWT_AUDIENCE: str = "momodu-api"

    # Google Basic OAuth #
        # Google OAuth settings
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8001/api/v1/auth/oauth/google/callback"
    
    # OAuth scopes
    GOOGLE_SCOPES: List[str] = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
    #_____________________________________________________


    # Encryption key for tokens (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())")
    ENCRYPTION_KEY: str = "change-this-in-production"

    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/momodu"

    # External services
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1/chat/completions"
    LINKEDIN_BASE_URL: str = "https://api.linkedin.com/v2"
    TELEGRAM_BASE_URL: str = "https://api.telegram.org"
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_BOT_USERNAME: str = "momoduxp_bot"
    PUBLIC_API_BASE_URL: Optional[str] = None

    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        """Get Celery broker URL from Redis settings."""
        return self.REDIS_URL

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS origins string to list."""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

# __________________________________ 
# Oauth Properties
    @property
    def google_oauth_config(self) -> dict:
        """Google OAuth configuration dict for authlib."""
        return {
            "client_id": self.GOOGLE_CLIENT_ID,
            "client_secret": self.GOOGLE_CLIENT_SECRET,
            "redirect_uri": self.GOOGLE_REDIRECT_URI,
            "scope": self.GOOGLE_SCOPES,
            "issuer": "https://accounts.google.com",
            "access_token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        }


# Global settings instance
api_settings = APISettings()
