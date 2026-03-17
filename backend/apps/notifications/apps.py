from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Notifications app configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'
