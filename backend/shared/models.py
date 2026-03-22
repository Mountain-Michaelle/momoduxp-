"""
SQLAlchemy ORM models for FastAPI.
These mirror Django models for database operations in FastAPI.

Version: 1.0.0

NOTE: For better separation of concerns, import from specific modules:
    - from shared.models.users import User, SocialPlatformAccount
    - from shared.models.posts import ScheduledPost
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from shared.database import Base
import enum


# Re-export from separated modules for backward compatibility
# Users - version 1.0.0
from shared.models.users import (
    PlatformChoice,
    User,
    SocialPlatformAccount,
)

# Posts - version 1.0.0
from shared.models.posts import (
    PostStatus,
    ScheduledPost,
)

# Notifications - version 1.0.0
from shared.models.notifications import (
    NotificationConnection,
    NotificationConnectionRequest,
    NotificationWebhookEvent,
    NotificationDelivery,
)


__version__ = "1.0.0"
