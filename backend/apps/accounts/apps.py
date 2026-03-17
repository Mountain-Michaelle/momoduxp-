from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Accounts app configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Accounts'

    def ready(self):
        """
        Register admin classes with custom admin site.
        This is done in ready() to avoid circular import issues.
        """
        from apps.core.admin_site import momodu_admin_site
        from .models import User, SocialPlatformAccount, UsageQuota
        from .admin import UserAdmin, SocialPlatformAccountAdmin, UsageQuotaAdmin

        # Register only if admin site is available (avoid NoneType errors)
        if momodu_admin_site is not None:
            momodu_admin_site.register(User, UserAdmin)
            momodu_admin_site.register(SocialPlatformAccount, SocialPlatformAccountAdmin)
            momodu_admin_site.register(UsageQuota, UsageQuotaAdmin)
