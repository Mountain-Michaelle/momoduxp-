"""
OAuth Account SQLAlchemy Model.
Stores OAuth provider links for users (Google, GitHub, etc.)
"""

import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database import Base


class OAuthAccount(Base):
    """
    SQLAlchemy model for OAuth provider accounts.
    Links users to external OAuth providers (Google, GitHub, etc.)
    """
    
    __tablename__ = "accounts_oauthaccount"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User association
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    # OAuth provider (google, github, facebook, etc.)
    provider = Column(String(50), nullable=False)
    
    # Provider's user ID (Google sub, GitHub ID, etc.)
    provider_user_id = Column(String(255), nullable=False)
    
    # OAuth tokens
    access_token = Column(Text, nullable=False, default="")
    refresh_token = Column(Text, nullable=True)
    id_token = Column(Text, nullable=True)
    
    # Token expiration
    token_expires_at = Column(DateTime, nullable=True)
    
    # OAuth scopes (space-separated string)
    scope = Column(String(500), nullable=False, default="")
    
    # Provider-specific extra data
    extra_data = Column(Text, nullable=True)  # JSON string for extra provider data
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # ─────────────────────────────────────────────────────────
    # Indexes for fast lookups
    # ─────────────────────────────────────────────────────────
    __table_args__ = (
        # Find OAuth account by provider + provider_user_id (login lookup)
        Index("oauth_provider_user_idx", "provider", "provider_user_id", unique=True),
        # Find all OAuth accounts for a user
        Index("oauth_user_idx", "user_id", "provider"),
        # Find active OAuth accounts for user
        Index("oauth_user_active_idx", "user_id", "provider", "is_active"),
    )
    
    # ─────────────────────────────────────────────────────────
    # Relationships
    # ─────────────────────────────────────────────────────────
    
    # Back reference to User (if needed)
    # user = relationship("User", backref="oauth_accounts")
    
    def __repr__(self):
        return f"<OAuthAccount user_id={self.user_id} provider={self.provider}>"
    
    @property
    def is_token_expired(self) -> bool:
        """Check if the access token is expired."""
        if not self.token_expires_at:
            return False  # No expiration, assume valid
        return datetime.utcnow() > self.token_expires_at
    
    def to_dict(self) -> dict:
        """Convert to dictionary (without sensitive tokens)."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "provider": self.provider,
            "provider_user_id": self.provider_user_id,
            "scope": self.scope,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }