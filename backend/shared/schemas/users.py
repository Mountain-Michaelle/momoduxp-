"""
User and Authentication Pydantic schemas.

This module contains all user-related schemas for the FastAPI application.
Version: 1.0.0
"""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ==============================================================================
# User Enums
# ==============================================================================

class SubscriptionPlan(str, Enum):
    """Subscription plan enumeration."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ==============================================================================
# Base Schema
# ==============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ==============================================================================
# User Schemas
# ==============================================================================

class UserBase(BaseSchema):
    """Base user schema."""
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters",
    )

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        # bcrypt hard limit
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Invalid password format")
        return value


class UserUpdate(BaseSchema):
    """Schema for updating a user."""
    username: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: uuid.UUID
    is_active: bool
    subscription_plan: SubscriptionPlan
    created_at: datetime
    updated_at: datetime


class UserWithQuota(UserResponse):
    """User response with usage quota info."""
    posts_used: int
    posts_limit: int
    ai_used: int
    ai_limit: int


# ==============================================================================
# Social Platform Account Schemas
# ==============================================================================

class Platform(str, Enum):
    """Social platform enumeration."""
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


class SocialAccountBase(BaseSchema):
    """Base social platform account schema."""
    platform: Platform
    platform_user_id: str


class SocialAccountCreate(SocialAccountBase):
    """Schema for creating a social platform account."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class SocialAccountResponse(SocialAccountBase):
    """Schema for social platform account response."""
    id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


__version__ = "1.0.0"

__all__ = [
    # Base
    "BaseSchema",
    # Enums
    "SubscriptionPlan",
    "Platform",
    # User schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserWithQuota",
    # Social account schemas
    "SocialAccountBase",
    "SocialAccountCreate",
    "SocialAccountResponse",
]
