from django.apps import AppConfig


class PostsConfig(AppConfig):
    """Posts app configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.posts'
    verbose_name = 'Posts'

    def ready(self):
        """
        Register admin classes with custom admin site.
        This is done in ready() to avoid circular import issues.
        """
        from apps.core.admin_site import momodu_admin_site
        from .models import ScheduledPost
        from .admin import ScheduledPostAdmin

        # Register only if admin site is available (avoid NoneType errors)
        if momodu_admin_site is not None:
            momodu_admin_site.register(ScheduledPost, ScheduledPostAdmin)
