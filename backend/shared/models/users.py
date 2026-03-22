"""
User SQLAlchemy models.

This module contains all user-related SQLAlchemy ORM models.
These mirror Django models for database operations in FastAPI.
Version: 1.0.0
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from shared.database import Base


# ==============================================================================
# Enums
# ==============================================================================

class PlatformChoice(str, enum.Enum):
    """Social platform choices."""
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


# ==============================================================================
# User Models
# ==============================================================================

class User(Base):
    """SQLAlchemy User model mirroring Django's User model."""
    
    __tablename__ = "accounts_user"
    
    # Root cause of DatatypeMismatchError: DB column is UUID, so ORM type must also be UUID.
    # If this is String/VARCHAR, asyncpg emits "$1::VARCHAR" and Postgres rejects INSERTs.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(254), unique=True, nullable=False)
    # DB has NOT NULL subscription_plan; include it in ORM so inserts don't send NULL.
    subscription_plan = Column(String(20), nullable=False, default="free")
    subscription_expires_at = Column(DateTime, nullable=True)
    password = Column(String(128), nullable=False)
    first_name = Column(String(150), nullable=True)
    last_name = Column(String(150), nullable=True)
    is_staff = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    date_joined = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    social_accounts = relationship("SocialPlatformAccount", back_populates="user", cascade="all, delete")
    notification_connections = relationship(
        "NotificationConnection",
        back_populates="user",
        cascade="all, delete",
    )
    notification_webhook_events = relationship(
        "NotificationWebhookEvent",
        back_populates="user",
    )
    notification_deliveries = relationship(
        "NotificationDelivery",
        back_populates="user",
    )
    
    def __repr__(self):
        return f"<User {self.username}>"


class SocialPlatformAccount(Base):
    """SQLAlchemy SocialPlatformAccount model."""
    
    __tablename__ = "accounts_socialplatformaccount"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("accounts_user.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(20), nullable=False)
    platform_user_id = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="social_accounts")
    posts = relationship("ScheduledPost", back_populates="account", cascade="all, delete")
    
    def __repr__(self):
        return f"<SocialPlatformAccount {self.platform}:{self.platform_user_id}>"


__version__ = "1.0.0"

__all__ = [
    # Enums
    "PlatformChoice",
    # Models
    "User",
    "SocialPlatformAccount",
]
