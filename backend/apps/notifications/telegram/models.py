"""
Backward-compatible imports for older Telegram-specific references.

The canonical notification models now live in apps.notifications.models.
"""

from apps.notifications.models import (  # noqa: F401
    NotificationConnection as TelegramNotificationConnection,
    NotificationWebhookEvent as TelegramWebhookEvent,
)
