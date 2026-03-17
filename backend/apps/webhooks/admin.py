"""
Django Admin configuration for Webhooks app.
Production-ready with monitoring, filters, and delivery tracking.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import WebhookEvent

from apps.core.admin_site import momodu_admin_site


class WebhookEndpointAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for Webhooks app.
    Production-ready with monitoring, filters, and delivery tracking.
    """
    list_display = (
        'user_email',
        'url_preview',
        'events_list',
        'status_indicator',
        'failure_count',
        'last_failure',
        'created_at',
    )

    list_filter = (
        'is_active',
        'events',
        'created_at',
        'last_failure',
    )

    search_fields = (
        'user__email',
        'url',
    )

    ordering = ('-created_at',)
    raw_id_fields = ('user',)

    readonly_fields = (
        'secret',
        'failure_count',
        'last_failure',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Endpoint Info', {
            'fields': ('user', 'url', 'secret', 'is_active'),
        }),
        ('Events', {
            'fields': ('events',),
        }),
        ('Statistics', {
            'fields': ('failure_count', 'last_failure'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.admin_order_field = 'user__email'
    user_email.short_description = 'User'

    def url_preview(self, obj):
        preview = obj.url[:40] + '...' if len(obj.url) > 40 else obj.url
        return format_html(
            '<code style="font-size:11px;">{}</code>',
            preview
        )
    url_preview.short_description = 'URL'

    def events_list(self, obj):
        badges = []
        for event in obj.events:
            badges.append(format_html(
                '<span style="background:#4f46e5;color:#fff;'
                'padding:2px 6px;border-radius:4px;font-size:10px;">{}</span>',
                event
            ))
        return format_html(' '.join(badges))
    events_list.short_description = 'Events'

    def status_indicator(self, obj):
        if not obj.is_active:
            return format_html('<span style="color:#9e9e9e;">● Inactive</span>')
        if obj.failure_count >= 5:
            return format_html('<span style="color:#f87171;">● Failing</span>')
        if obj.failure_count > 0:
            return format_html('<span style="color:#fbbf24;">● Issues</span>')
        return format_html('<span style="color:#a3e635;">● Healthy</span>')

    actions = ('activate_endpoints', 'deactivate_endpoints')

    def activate_endpoints(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Endpoints activated.")

    def deactivate_endpoints(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Endpoints deactivated.")


class WebhookDeliveryAdmin(admin.ModelAdmin):
    """
    Admin for webhook delivery logs with monitoring.
    """

    list_display = (
        'delivery_status',
        'event_badge',
        'endpoint_url',
        'http_status',
        'duration',
        'created_at',
    )

    list_filter = (
        'succeeded',
        'event',
        'status_code',
        'created_at',
    )

    search_fields = (
        'endpoint__user__email',
        'endpoint__url',
        'error_message',
    )

    ordering = ('-created_at',)

    raw_id_fields = ('endpoint',)

    readonly_fields = (
        'endpoint',
        'event',
        'payload',
        'status_code',
        'response_body',
        'error_message',
        'succeeded',
        'duration_ms',
        'created_at',
    )

    def delivery_status(self, obj):
        """Show delivery status."""
        if obj.succeeded:
            color = '#a3e635'  # Green
            text = 'Success'
        else:
            color = '#f87171'  # Red
            text = 'Failed'
        return format_html(
            '<span style="color: {};">● {}</span>',
            color,
            text
        )
    delivery_status.short_description = 'Status'

    def event_badge(self, obj):
        """Show event as badge."""
        colors = {
            'post.created': '#4f46e5',  # Indigo-600
            'post.updated': '#a3e635',  # Green
            'post.published': '#818cf8',  # Indigo-400
            'post.failed': '#f87171',  # Red
            'approval.approved': '#a3e635',  # Green
            'approval.rejected': '#fbbf24',  # Orange
        }
        color = colors.get(obj.event, '#9e9e9e')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.event
        )
    event_badge.short_description = 'Event'

    def endpoint_url(self, obj):
        """Show endpoint URL."""
        url = obj.endpoint.url
        preview = url[:30] + '...' if len(url) > 30 else url
        return format_html(
            '<a href="{}" target="_blank" style="color: #4f46e5;">{}</a>',
            url,
            preview
        )
    endpoint_url.short_description = 'Endpoint'

    def http_status(self, obj):
        """Show HTTP status code."""
        if obj.status_code:
            if obj.status_code >= 200 and obj.status_code < 300:
                color = '#a3e635'
            elif obj.status_code >= 400:
                color = '#f87171'
            else:
                color = '#fbbf24'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color,
                obj.status_code
            )
        return '-'
    http_status.short_description = 'HTTP'

    def duration(self, obj):
        """Show response duration."""
        if obj.duration_ms:
            if obj.duration_ms < 1000:
                color = '#a3e635'
                text = f'{obj.duration_ms}ms'
            elif obj.duration_ms < 5000:
                color = '#fbbf24'
                text = f'{obj.duration_ms}ms'
            else:
                color = '#f87171'
                text = f'{obj.duration_ms}ms'
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                text
            )
        return '-'
    duration.short_description = 'Duration'

    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related(
            'endpoint', 'endpoint__user'
        )


# WebhookEvent is read-only, just display it
momodu_admin_site.register(WebhookEvent)
