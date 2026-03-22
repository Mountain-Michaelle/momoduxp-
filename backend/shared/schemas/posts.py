"""
Post Pydantic schemas.

This module contains all post-related schemas for the FastAPI application.
Version: 1.0.0
"""

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, Field, HttpUrl
from enum import Enum


# ==============================================================================
# Post Enums
# ==============================================================================

class PostStatus(str, Enum):
    """Post status enumeration."""
    DRAFT = "draft"
    SENT_FOR_APPROVAL = "sent_for_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


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
# Post Schemas
# ==============================================================================

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


__version__ = "1.0.0"

__all__ = [
    # Enums
    "PostStatus",
    # Base
    "BaseSchema",
    # Post schemas
    "PostBase",
    "PostCreate",
    "PostUpdate",
    "PostResponse",
    "PostSubmitRequest",
    "PostActionResponse",
]
