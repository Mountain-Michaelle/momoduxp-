"""
Shared Pydantic schemas for FastAPI.
These schemas mirror Django models for API validation.
DRY: Centralized schema definitions used by both Django and FastAPI.
"""

from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
from enum import Enum
import uuid


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
# User & Authentication Schemas
# ==============================================================================

class SubscriptionPlan(str, Enum):
    """Subscription plan enumeration."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


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


# ==============================================================================
# Post Schemas
# ==============================================================================

class PostStatus(str, Enum):
    """Post status enumeration."""
    DRAFT = "draft"
    SENT_FOR_APPROVAL = "sent_for_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


class PostBase(BaseSchema):
    """Base post schema."""
    content: str
    media_urls: List[HttpUrl] = Field(default_factory=list)
    scheduled_for: datetime
    approval_deadline: Optional[datetime] = None


class PostCreate(PostBase):
    """Schema for creating a post."""
    account_id: uuid.UUID


class PostUpdate(BaseSchema):
    """Schema for updating a post."""
    content: Optional[str] = None
    media_urls: Optional[List[HttpUrl]] = None
    scheduled_for: Optional[datetime] = None
    approval_deadline: Optional[datetime] = None
    status: Optional[PostStatus] = None


class PostResponse(PostBase):
    """Schema for post response."""
    id: uuid.UUID
    author_id: uuid.UUID
    account_id: uuid.UUID
    status: PostStatus
    approved_at: Optional[datetime] = None
    external_post_id: Optional[str] = None
    platform_id: Optional[str] = None
    error_log: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PostSubmitRequest(BaseSchema):
    """Request to submit post for approval."""
    approval_deadline: Optional[datetime] = None


class PostActionResponse(BaseSchema):
    """Response for post action (approve/reject)."""
    success: bool
    message: str
    post: PostResponse


# ==============================================================================
# AI Processing Schemas
# ==============================================================================

class AITone(str, Enum):
    """AI content tone options."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    INSPIRING = "inspiring"
    HUMOROUS = "humorous"


class AIRequest(BaseSchema):
    """Schema for AI processing request."""
    prompt: str
    content_type: str = "post"
    platform: Optional[Platform] = None
    tone: Optional[AITone] = None
    max_tokens: int = 500


class AIResponse(BaseSchema):
    """Schema for AI processing response."""
    generated_content: str
    model_used: str
    tokens_used: int


class AIVariationRequest(BaseSchema):
    """Request for generating multiple variations."""
    content: str
    count: int = Field(default=3, ge=1, le=5)


# ==============================================================================
# Authentication Schemas
# ==============================================================================

class Token(BaseSchema):
    """Schema for JWT token response."""
    access_token: str
    refresh_token: str
    user_id: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseSchema):
    """Schema for token payload."""
    user_id: Optional[uuid.UUID] = None
    exp: Optional[datetime] = None
    type: Optional[str] = None


class LoginRequest(BaseSchema):
    """Schema for login request."""
    username: str
    password: str


class TokenRefreshRequest(BaseSchema):
    """Schema for token refresh request."""
    refresh_token: str


# ==============================================================================
# Usage & Quota Schemas
# ==============================================================================

class UsageQuotaResponse(BaseSchema):
    """Schema for usage quota response."""
    posts_used: int
    posts_limit: int
    ai_used: int
    ai_limit: int
    webhooks_used: int
    webhooks_limit: int
    reset_date: Optional[datetime] = None


class PlanDetails(BaseSchema):
    """Schema for plan details."""
    name: SubscriptionPlan
    posts_limit: int
    ai_limit: int
    webhooks_limit: int
    price_monthly: Optional[float] = None


# ==============================================================================
# Webhook Schemas
# ==============================================================================

class WebhookEventType(str, Enum):
    """Webhook event types."""
    POST_CREATED = "post.created"
    POST_UPDATED = "post.updated"
    POST_PUBLISHED = "post.published"
    POST_FAILED = "post.failed"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"


class WebhookCreate(BaseSchema):
    """Schema for creating a webhook endpoint."""
    url: HttpUrl
    events: List[WebhookEventType]
    secret: Optional[str] = None  # Auto-generated if not provided


class WebhookResponse(BaseSchema):
    """Schema for webhook endpoint response."""
    id: uuid.UUID
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime


class WebhookDeliveryResponse(BaseSchema):
    """Schema for webhook delivery response."""
    id: uuid.UUID
    event: str
    status_code: Optional[int] = None
    succeeded: bool
    duration_ms: Optional[int] = None
    created_at: datetime


# ==============================================================================
# Pagination Schemas
# ==============================================================================

class PaginationParams(BaseSchema):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseSchema):
    """Paginated response wrapper."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int


# ==============================================================================
# Health Check Schemas
# ==============================================================================

class HealthCheck(BaseSchema):
    """Schema for health check response."""
    status: str
    database: str
    redis: str
    celery: str
    version: str = "1.0.0"


class HealthCheckDetailed(HealthCheck):
    """Schema for detailed health check response."""
    dependencies: dict
    uptime_seconds: float
