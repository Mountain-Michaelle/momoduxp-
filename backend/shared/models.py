"""
SQLAlchemy ORM models for FastAPI.
These mirror Django models for database operations in FastAPI.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.database import Base
import enum


class PostStatus(str, enum.Enum):
    """Post status enumeration matching Django."""
    DRAFT = "draft"
    SENT_FOR_APPROVAL = "sent_for_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


class PlatformChoice(str, enum.Enum):
    """Social platform choices."""
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"


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


class ScheduledPost(Base):
    """SQLAlchemy ScheduledPost model mirroring Django's ScheduledPost."""
    
    __tablename__ = "posts_scheduledpost"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id = Column(UUID(as_uuid=True), ForeignKey("accounts_user.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts_socialplatformaccount.id", ondelete="CASCADE"), nullable=False)
    
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
