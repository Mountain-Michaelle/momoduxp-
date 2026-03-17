"""
Shared utilities for encryption, formatting, and common operations.
DRY: Used by both Django and FastAPI.
"""

from cryptography.fernet import Fernet
from datetime import datetime, timezone
from typing import Any, Optional
import uuid
import base64
import hashlib


# Token encryption/decryption
def get_encryption_key() -> bytes:
    """Get encryption key from environment."""
    import os
    from django.conf import settings
    key = os.environ.get('ENCRYPTION_KEY', settings.ENCRYPTION_KEY)
    return key.encode()


def encrypt_token(token: str) -> str:
    """Encrypt sensitive tokens (social account tokens, etc.)."""
    fernet = Fernet(get_encryption_key())
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt tokens."""
    fernet = Fernet(get_encryption_key())
    return fernet.decrypt(encrypted.encode()).decode()


# UUID utilities
def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def parse_uuid(value: str) -> Optional[uuid.UUID]:
    """Parse UUID string, return None on failure."""
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


# Date/time utilities
def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def format_datetime(dt: datetime, format: str = "%Y-%m-%dT%H:%M:%SZ") -> str:
    """Format datetime to ISO string."""
    return dt.strftime(format)


def parse_datetime(value: str) -> Optional[datetime]:
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


# String utilities
def slugify(text: str) -> str:
    """Create URL-safe slug from text."""
    return text.lower().replace(' ', '-').replace('_', '-')


def truncate(text: str, max_length: int = 100, suffix: str = '...') -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# Dictionary utilities
def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def dict_without_none(data: dict) -> dict:
    """Remove None values from dictionary."""
    return {k: v for k, v in data.items() if v is not None}


# Validation utilities
def validate_url(url: str) -> bool:
    """Basic URL validation."""
    return url.startswith('http://') or url.startswith('https://')


# Hash utilities (for non-sensitive hashing)
def hash_string(text: str, length: int = 8) -> str:
    """Create short hash of string."""
    return hashlib.md5(text.encode()).hexdigest()[:length]


# Async utilities
async def gather_tasks(*tasks):
    """Run multiple async tasks concurrently."""
    import asyncio
    return await asyncio.gather(*tasks, return_exceptions=True)


# Constants
class PlanLimits:
    """Usage limits per subscription plan."""

    FREE = {'posts': 10, 'ai_generations': 5}
    PRO = {'posts': 100, 'ai_generations': 50}
    ENTERPRISE = {'posts': -1, 'ai_generations': -1}  # unlimited

    @classmethod
    def get_limit(cls, plan: str, resource: str) -> int:
        return cls.__dict__.get(plan.upper(), cls.FREE).get(resource, 0)


class PostStatus:
    """Post status constants - DRY for both Django and FastAPI."""

    DRAFT = "draft"
    SENT_FOR_APPROVAL = "sent_for_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"

    CHOICES = [
        (DRAFT, "Draft"),
        (SENT_FOR_APPROVAL, "Sent for Approval"),
        (APPROVED, "Approved"),
        (PUBLISHED, "Published"),
        (FAILED, "Failed"),
    ]


class Platform:
    """Social platform constants."""

    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"

    CHOICES = [
        (LINKEDIN, "LinkedIn"),
        (TWITTER, "Twitter"),
        (FACEBOOK, "Facebook"),
        (INSTAGRAM, "Instagram"),
    ]
