from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.webhooks'
    verbose_name = 'Webhooks'

    def ready(self):
        """
        Register admin classes with custom admin site.
        This is done in ready() to avoid circular import issues.
        """
        from apps.core.admin_site import momodu_admin_site
        from .models import WebhookEndpoint, WebhookDelivery, WebhookEvent
        from .admin import WebhookEndpointAdmin, WebhookDeliveryAdmin  

        # Register only if admin site is available (avoid NoneType errors)
        if momodu_admin_site is not None:
            momodu_admin_site.register(WebhookEndpoint, WebhookEndpointAdmin)
            momodu_admin_site.register(WebhookDelivery, WebhookDeliveryAdmin)

            # Add other registrations as needed
