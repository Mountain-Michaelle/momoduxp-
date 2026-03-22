from django.contrib import admin

from apps.core.admin_site import momodu_admin_site
from apps.notifications.models import (
    NotificationConnection,
    NotificationConnectionRequest,
    NotificationDelivery,
    NotificationWebhookEvent,
)


@admin.register(NotificationConnection, site=momodu_admin_site)
class NotificationConnectionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "platform",
        "destination_type",
        "destination",
        "is_primary",
        "is_verified",
        "is_active",
        "last_interaction_at",
    )
    list_filter = ("platform", "destination_type", "is_primary", "is_verified", "is_active")
    search_fields = (
        "user__email",
        "user__username",
        "destination",
        "external_user_id",
        "external_channel_id",
        "display_name",
    )
    readonly_fields = ("connected_at", "last_interaction_at", "created_at", "updated_at")


@admin.register(NotificationWebhookEvent, site=momodu_admin_site)
class NotificationWebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "platform",
        "event_type",
        "direction",
        "user",
        "destination",
        "processed",
        "processed_at",
        "created_at",
    )
    list_filter = ("platform", "direction", "processed", "created_at")
    search_fields = (
        "external_event_id",
        "destination",
        "external_user_id",
        "connection__user__email",
        "user__email",
    )
    readonly_fields = ("payload", "metadata", "processed_at", "created_at", "updated_at")


@admin.register(NotificationDelivery, site=momodu_admin_site)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "platform",
        "notification_type",
        "user",
        "status",
        "provider_message_id",
        "sent_at",
        "failed_at",
        "created_at",
    )
    list_filter = ("platform", "status", "created_at")
    search_fields = (
        "notification_type",
        "provider_message_id",
        "connection__destination",
        "user__email",
    )
    readonly_fields = (
        "payload",
        "metadata",
        "sent_at",
        "delivered_at",
        "failed_at",
        "created_at",
        "updated_at",
    )


@admin.register(NotificationConnectionRequest, site=momodu_admin_site)
class NotificationConnectionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "platform",
        "reference_id",
        "expires_at",
        "used_at",
        "created_at",
    )
    list_filter = ("platform", "created_at", "expires_at", "used_at")
    search_fields = ("user__email", "user__username", "reference_id")
    readonly_fields = ("reference_id", "expires_at", "used_at", "metadata", "created_at", "updated_at")
