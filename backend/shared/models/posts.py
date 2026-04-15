"""
Post SQLAlchemy models.

This module contains all post-related SQLAlchemy ORM models.
These mirror Django models for database operations in FastAPI.
Version: 1.0.0
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from shared.database import Base


# ==============================================================================
# Enums
# ==============================================================================


class PostStatus(str, enum.Enum):
    """Post status enumeration matching Django."""

    DRAFT = "draft"
    SENT_FOR_APPROVAL = "sent_for_approval"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


# ==============================================================================
# Post Models
# ==============================================================================


class ScheduledPost(Base):
    """SQLAlchemy ScheduledPost model mirroring Django's ScheduledPost."""

    __tablename__ = "posts_scheduledpost"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts_socialplatformaccount.id", ondelete="CASCADE"),
        nullable=False,
    )

    content = Column(Text, nullable=False)
    media_urls = Column(JSON, default=list)

    status = Column(String(32), default=PostStatus.DRAFT.value)

    scheduled_for = Column(DateTime, nullable=False)
    approval_deadline = Column(DateTime, nullable=False)
    approved_at = Column(DateTime, nullable=True)

    external_post_id = Column(String(255), nullable=True)
    platform_id = Column(String(255), nullable=True)
    error_log = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = relationship("User", foreign_keys=[author_id])
    account = relationship("SocialPlatformAccount", back_populates="posts")

    def __repr__(self):
        return f"<ScheduledPost {self.id} - {self.status}>"


__version__ = "1.0.0"

__all__ = [
    # Enums
    "PostStatus",
    # Models
    "ScheduledPost",
]
