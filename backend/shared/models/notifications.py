"""
Generic notification SQLAlchemy models.

These mirror Django notification models for FastAPI database operations.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database import Base


class NotificationConnection(Base):
    """SQLAlchemy mirror of the Django generic notification connection model."""

    __tablename__ = "notifications_notificationconnection"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("accounts_user.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(32), nullable=False)
    destination_type = Column(String(32), nullable=False, default="custom")
    destination = Column(String(255), nullable=False)
    external_user_id = Column(String(255), nullable=False, default="")
    external_channel_id = Column(String(255), nullable=False, default="")
    display_name = Column(String(255), nullable=False, default="")
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    is_verified = Column(Boolean, nullable=False, default=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    connected_at = Column(DateTime, nullable=True)
    last_interaction_at = Column(DateTime, nullable=True)
    last_inbound_event_id = Column(String(255), nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="notification_connections")
    webhook_events = relationship("NotificationWebhookEvent", back_populates="connection")
    deliveries = relationship("NotificationDelivery", back_populates="connection")

    __table_args__ = (
        Index("notif_conn_user_platform_idx", "user_id", "platform"),
        Index("notif_conn_platform_user_idx", "platform", "external_user_id"),
        Index("notif_conn_plat_chan_idx", "platform", "external_channel_id"),
    )


class NotificationWebhookEvent(Base):
    """SQLAlchemy mirror of the Django generic notification webhook event model."""

    __tablename__ = "notifications_notificationwebhookevent"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notifications_notificationconnection.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("accounts_user.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(32), nullable=False)
    event_type = Column(String(64), nullable=False, default="unknown")
    direction = Column(String(16), nullable=False, default="inbound")
    external_event_id = Column(String(255), nullable=False, default="")
    destination = Column(String(255), nullable=False, default="")
    external_user_id = Column(String(255), nullable=False, default="")
    payload = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    processed = Column(Boolean, nullable=False, default=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connection = relationship("NotificationConnection", back_populates="webhook_events")
    user = relationship("User", back_populates="notification_webhook_events")

    __table_args__ = (
        Index("notif_event_platform_user_idx", "platform", "external_user_id"),
        Index("notif_event_platform_dest_idx", "platform", "destination"),
    )


class NotificationDelivery(Base):
    """SQLAlchemy mirror of the Django generic notification delivery model."""

    __tablename__ = "notifications_notificationdelivery"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notifications_notificationconnection.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("accounts_user.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(32), nullable=False)
    notification_type = Column(String(64), nullable=False)
    subject = Column(String(255), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    payload = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    status = Column(String(16), nullable=False, default="pending")
    provider_message_id = Column(String(255), nullable=False, default="")
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connection = relationship("NotificationConnection", back_populates="deliveries")
    user = relationship("User", back_populates="notification_deliveries")

    __table_args__ = (
        Index("notif_delivery_user_status_idx", "user_id", "status"),
        Index("notif_deliv_plat_status_idx", "platform", "status"),
    )


class NotificationConnectionRequest(Base):
    """SQLAlchemy mirror of the one-time notification connection request model."""

    __tablename__ = "notifications_notificationconnectionrequest"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("accounts_user.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(32), nullable=False)
    reference_id = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        Index("notif_req_user_platform_idx", "user_id", "platform"),
        Index("notif_req_plat_ref_idx", "platform", "reference_id"),
        Index("notif_req_exp_idx", "expires_at"),
    )


__all__ = [
    "NotificationConnection",
    "NotificationWebhookEvent",
    "NotificationDelivery",
    "NotificationConnectionRequest",
]
