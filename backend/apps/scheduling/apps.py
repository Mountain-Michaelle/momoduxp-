from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    """Scheduling app configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scheduling'
    verbose_name = 'Scheduling'
