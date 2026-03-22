"""
Shared Pydantic schema exports for FastAPI.
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import Field
from enum import Enum

from shared.schemas.users import (
    BaseSchema,
    Platform,
    SocialAccountBase,
    SocialAccountCreate,
    SocialAccountResponse,
    SubscriptionPlan,
    UserBase,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithQuota,
)
from shared.schemas.posts import (
    PostActionResponse,
    PostBase,
    PostCreate,
    PostResponse,
    PostStatus,
    PostSubmitRequest,
    PostUpdate,
)
from shared.schemas.notifications import (
    NotificationConnectionResponse,
    NotificationWebhookEventResponse,
    NotificationDeliveryResponse,
    NotificationWebhookReceiveResponse,
    TelegramConnectLinkResponse,
    TelegramNotificationSendRequest,
    TelegramNotificationSendResponse,
)


class AITone(str, Enum):
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    INSPIRING = "inspiring"
    HUMOROUS = "humorous"


class AIRequest(BaseSchema):
    prompt: str
    content_type: str = "post"
    platform: Optional[Platform] = None
    tone: Optional[AITone] = None
    max_tokens: int = 500


class AIResponse(BaseSchema):
    generated_content: str
    model_used: str
    tokens_used: int


class AIVariationRequest(BaseSchema):
    content: str
    count: int = Field(default=3, ge=1, le=5)


class Token(BaseSchema):
    access_token: str
    refresh_token: str
    user_id: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseSchema):
    user_id: Optional[uuid.UUID] = None
    exp: Optional[datetime] = None
    type: Optional[str] = None


class LoginRequest(BaseSchema):
    username: str
    password: str


class TokenRefreshRequest(BaseSchema):
    refresh_token: str


class UsageQuotaResponse(BaseSchema):
    posts_used: int
    posts_limit: int
    ai_used: int
    ai_limit: int
    webhooks_used: int
    webhooks_limit: int
    reset_date: Optional[datetime] = None


class PlanDetails(BaseSchema):
    name: SubscriptionPlan
    posts_limit: int
    ai_limit: int
    webhooks_limit: int
    price_monthly: Optional[float] = None


class WebhookEventType(str, Enum):
    POST_CREATED = "post.created"
    POST_UPDATED = "post.updated"
    POST_PUBLISHED = "post.published"
    POST_FAILED = "post.failed"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"


class WebhookCreate(BaseSchema):
    url: str
    events: list[WebhookEventType]
    secret: Optional[str] = None


class WebhookResponse(BaseSchema):
    id: uuid.UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime


class WebhookDeliveryResponse(BaseSchema):
    id: uuid.UUID
    event: str
    status_code: Optional[int] = None
    succeeded: bool
    duration_ms: Optional[int] = None
    created_at: datetime


class PaginationParams(BaseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseSchema):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


class HealthCheck(BaseSchema):
    status: str
    database: str
    redis: str
    celery: str
    version: str = "1.0.0"


class HealthCheckDetailed(HealthCheck):
    dependencies: dict[str, Any]
    uptime_seconds: float


__all__ = [
    "BaseSchema",
    "SubscriptionPlan",
    "Platform",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserWithQuota",
    "SocialAccountBase",
    "SocialAccountCreate",
    "SocialAccountResponse",
    "PostStatus",
    "PostBase",
    "PostCreate",
    "PostUpdate",
    "PostResponse",
    "PostSubmitRequest",
    "PostActionResponse",
    "NotificationConnectionResponse",
    "NotificationWebhookEventResponse",
    "NotificationDeliveryResponse",
    "NotificationWebhookReceiveResponse",
    "TelegramConnectLinkResponse",
    "TelegramNotificationSendRequest",
    "TelegramNotificationSendResponse",
    "AITone",
    "AIRequest",
    "AIResponse",
    "AIVariationRequest",
    "Token",
    "TokenData",
    "LoginRequest",
    "TokenRefreshRequest",
    "UsageQuotaResponse",
    "PlanDetails",
    "WebhookEventType",
    "WebhookCreate",
    "WebhookResponse",
    "WebhookDeliveryResponse",
    "PaginationParams",
    "PaginatedResponse",
    "HealthCheck",
    "HealthCheckDetailed",
]
