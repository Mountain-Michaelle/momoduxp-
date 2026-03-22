from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import BaseModel


class NotificationPlatform(models.TextChoices):
    TELEGRAM = "telegram", "Telegram"
    EMAIL = "email", "Email"
    WHATSAPP = "whatsapp", "WhatsApp"
    SMS = "sms", "SMS"
    PUSH = "push", "Push"
    WEBHOOK = "webhook", "Webhook"
    CUSTOM = "custom", "Custom"


class NotificationDestinationType(models.TextChoices):
    CHAT = "chat", "Chat"
    EMAIL = "email", "Email"
    PHONE = "phone", "Phone"
    WEBHOOK = "webhook", "Webhook"
    DEVICE = "device", "Device"
    CUSTOM = "custom", "Custom"


class NotificationEventDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class NotificationDeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    DELIVERED = "delivered", "Delivered"
    READ = "read", "Read"


class NotificationConnection(BaseModel):
    """A user notification endpoint for any supported platform."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notification_connections",
    )
    platform = models.CharField(
        max_length=32,
        choices=NotificationPlatform.choices,
    )
    destination_type = models.CharField(
        max_length=32,
        choices=NotificationDestinationType.choices,
        default=NotificationDestinationType.CUSTOM,
    )
    destination = models.CharField(
        max_length=255,
        help_text="The provider destination such as email, phone, chat id, or webhook URL.",
    )
    external_user_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Provider user identifier when available.",
    )
    external_channel_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Provider chat, room, or channel identifier when available.",
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific metadata stored without changing the schema.",
    )
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(
        default=False,
        help_text="Only one active primary notification method is allowed per user.",
    )
    connected_at = models.DateTimeField(null=True, blank=True)
    last_interaction_at = models.DateTimeField(null=True, blank=True)
    last_inbound_event_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-is_primary", "platform", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "platform", "destination"],
                name="unique_notification_connection_per_destination",
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_primary=True, is_active=True),
                name="unique_active_primary_notification_connection_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "platform"], name="notif_conn_user_platform_idx"),
            models.Index(fields=["platform", "external_user_id"], name="notif_conn_platform_user_idx"),
            models.Index(fields=["platform", "external_channel_id"], name="notif_conn_plat_chan_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} [{self.platform}] -> {self.destination}"

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.connected_at is None:
            self.connected_at = now
        if self.is_primary and self.user_id:
            with transaction.atomic():
                type(self).objects.filter(
                    user_id=self.user_id,
                    is_primary=True,
                ).exclude(pk=self.pk).update(is_primary=False)
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    @classmethod
    def get_active_for_user(cls, user_id):
        return cls.objects.filter(user_id=user_id, is_active=True, is_primary=True).first()


class NotificationWebhookEvent(BaseModel):
    """Stores webhook events from any notification provider."""

    connection = models.ForeignKey(
        NotificationConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="webhook_events",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_webhook_events",
    )
    platform = models.CharField(max_length=32, choices=NotificationPlatform.choices)
    event_type = models.CharField(max_length=64, default="unknown")
    direction = models.CharField(
        max_length=16,
        choices=NotificationEventDirection.choices,
        default=NotificationEventDirection.INBOUND,
    )
    external_event_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Provider event id used for deduplication when available.",
    )
    destination = models.CharField(max_length=255, blank=True)
    external_user_id = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "external_event_id"],
                condition=~Q(external_event_id=""),
                name="unique_notification_webhook_event_per_platform",
            ),
        ]
        indexes = [
            models.Index(fields=["platform", "external_user_id"], name="notif_event_platform_user_idx"),
            models.Index(fields=["platform", "destination"], name="notif_event_platform_dest_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.platform}:{self.event_type}:{self.external_event_id or self.id}"

    def mark_processed(self) -> None:
        self.processed = True
        self.processed_at = timezone.now()
        self.error_message = ""
        self.save(update_fields=["processed", "processed_at", "error_message", "updated_at"])

    def mark_failed(self, error_message: str) -> None:
        self.processed = False
        self.error_message = error_message
        self.save(update_fields=["processed", "error_message", "updated_at"])


class NotificationDelivery(BaseModel):
    """Tracks outbound deliveries for any notification provider."""

    connection = models.ForeignKey(
        NotificationConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_deliveries",
    )
    platform = models.CharField(max_length=32, choices=NotificationPlatform.choices)
    notification_type = models.CharField(max_length=64)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=NotificationDeliveryStatus.choices,
        default=NotificationDeliveryStatus.PENDING,
    )
    provider_message_id = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"], name="notif_delivery_user_status_idx"),
            models.Index(fields=["platform", "status"], name="notif_deliv_plat_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.platform}:{self.notification_type}:{self.status}"

    def mark_sent(self, provider_message_id: str = "") -> None:
        self.status = NotificationDeliveryStatus.SENT
        self.provider_message_id = provider_message_id
        self.sent_at = timezone.now()
        self.error_message = ""
        self.save(update_fields=["status", "provider_message_id", "sent_at", "error_message", "updated_at"])

    def mark_delivered(self) -> None:
        self.status = NotificationDeliveryStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at", "updated_at"])

    def mark_failed(self, error_message: str) -> None:
        self.status = NotificationDeliveryStatus.FAILED
        self.failed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=["status", "failed_at", "error_message", "updated_at"])


class NotificationConnectionRequest(BaseModel):
    """One-time connection request used to link a user to a notification provider."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notification_connection_requests",
    )
    platform = models.CharField(max_length=32, choices=NotificationPlatform.choices)
    reference_id = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "platform"], name="notif_req_user_platform_idx"),
            models.Index(fields=["platform", "reference_id"], name="notif_req_plat_ref_idx"),
            models.Index(fields=["expires_at"], name="notif_req_exp_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} [{self.platform}] connect request"

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at", "updated_at"])
