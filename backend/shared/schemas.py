"""
Shared Pydantic schemas for FastAPI.
These schemas mirror Django models for API validation.
DRY: Centralized schema definitions used by both Django and FastAPI.

Version: 1.0.0

NOTE: For better separation of concerns, import from specific modules:
    - from shared.schemas.users import UserResponse, UserCreate, etc.
    - from shared.schemas.posts import PostResponse, PostCreate, etc.
"""

from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
from enum import Enum
import uuid

# Re-export from separated modules for backward compatibility
# Users and Posts - version 1.0.0
from shared.schemas.users import (
    BaseSchema,
    SubscriptionPlan,
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserWithQuota,
    Platform,
    SocialAccountBase,
    SocialAccountCreate,
    SocialAccountResponse,
)

from shared.schemas.posts import (
    PostStatus,
    PostBase,
    PostCreate,
    PostUpdate,
    PostResponse,
    PostSubmitRequest,
    PostActionResponse,
)

from shared.schemas.notifications import (
    NotificationConnectionResponse,
    NotificationWebhookEventResponse,
    NotificationDeliveryResponse,
    NotificationWebhookReceiveResponse,
    TelegramConnectLinkResponse,
    TelegramNotificationSendRequest,
    TelegramNotificationSendResponse,
    TelegramWebhookConfigResponse,
)


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


__version__ = "1.0.0"
