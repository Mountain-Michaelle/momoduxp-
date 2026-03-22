"""
Generic notification Pydantic schemas.
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class NotificationBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class NotificationConnectionResponse(NotificationBaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID
    platform: str
    destination_type: str
    destination: str
    external_user_id: str
    external_channel_id: str
    display_name: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    is_verified: bool
    is_primary: bool
    connected_at: Optional[datetime] = None
    last_interaction_at: Optional[datetime] = None
    last_inbound_event_id: str
    created_at: datetime
    updated_at: datetime


class NotificationWebhookEventResponse(NotificationBaseSchema):
    id: uuid.UUID
    connection_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    platform: str
    event_type: str
    direction: str
    external_event_id: str
    destination: str
    external_user_id: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    processed: bool
    processed_at: Optional[datetime] = None
    error_message: str
    created_at: datetime
    updated_at: datetime


class NotificationDeliveryResponse(NotificationBaseSchema):
    id: uuid.UUID
    connection_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    platform: str
    notification_type: str
    subject: str
    body: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    status: str
    provider_message_id: str
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: str
    created_at: datetime
    updated_at: datetime


class NotificationWebhookReceiveResponse(NotificationBaseSchema):
    ok: bool
    event: NotificationWebhookEventResponse
    connection: Optional[NotificationConnectionResponse] = None
    linked_user_id: Optional[uuid.UUID] = None
    action: Optional[str] = None
    action_reference: Optional[str] = None
    detail: str


class TelegramNotificationSendRequest(NotificationBaseSchema):
    message: str
    reference_id: str
    notification_type: str = "automation_control"
    connection_id: Optional[uuid.UUID] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelegramNotificationSendResponse(NotificationBaseSchema):
    ok: bool
    connection: NotificationConnectionResponse
    delivery: NotificationDeliveryResponse
    telegram_message_id: Optional[str] = None
    detail: str


class TelegramConnectLinkResponse(NotificationBaseSchema):
    ok: bool
    reference_id: str
    telegram_link: str
    expires_at: datetime
    detail: str


__all__ = [
    "NotificationConnectionResponse",
    "NotificationWebhookEventResponse",
    "NotificationDeliveryResponse",
    "NotificationWebhookReceiveResponse",
    "TelegramNotificationSendRequest",
    "TelegramNotificationSendResponse",
    "TelegramConnectLinkResponse",
]
