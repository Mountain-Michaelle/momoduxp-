"""
Django Admin configuration for Accounts app.
Production-ready with filters, search, actions, and detailed views.
"""

from django.contrib import admin

from .models import User, SocialPlatformAccount, UsageQuota, SubscriptionPlan

from apps.core.admin_site import momodu_admin_site

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone


class UserAdmin(BaseUserAdmin):
    """
    Custom User admin with advanced filtering and actions.
    Dark Indigo theme styling.
    """

    # List display configuration
    list_display = (
        'email',
        'username',
        'subscription_badge',
        'is_active',
        'is_subscription_active',
        'created_at',
    )

    # Fields to show in list view
    list_filter = (
        'subscription_plan',
        'is_active',
        'is_superuser',
        'created_at',
        'last_login',
    )

    # Search fields
    search_fields = ('email', 'username', 'first_name', 'last_name')

    # Default ordering
    ordering = ('-created_at',)

    # Fieldsets for edit page
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password'),
            'classes': ('VSCodeBlue',),
        }),
        ('Personal Info', {
            'fields': ('username', 'first_name', 'last_name'),
        }),
        ('Subscription', {
            'fields': ('subscription_plan', 'subscription_expires_at'),
            'classes': ('VSCodeBlue',),
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('VSCodeBlue',),
        }),
        ('Important Dates', {
            'fields': ('created_at', 'updated_at', 'last_login'),
            'classes': ('collapse',),
        }),
    )

    # Fields for add user page
    add_fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password1', 'password2'),
        }),
        ('Personal Info', {
            'fields': ('username', 'first_name', 'last_name'),
        }),
        ('Subscription', {
            'fields': ('subscription_plan',),
        }),
    )

    # Read-only fields
    readonly_fields = ('created_at', 'updated_at', 'last_login')

    # Custom methods
    def subscription_badge(self, obj):
        """Display subscription plan with color-coded badge."""
        colors = {
            'free': "#52047d",  # Indigo-600
            'pro': '#a3e635',   # Green
            'enterprise': '#fbbf24',  # Orange
        }
        color = colors.get(obj.subscription_plan, '#4f46e5')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 12px;">{}</span>',
            color,
            obj.get_subscription_plan_display()
        )
    subscription_badge.short_description = 'Plan'

    def is_subscription_active(self, obj):
        """Check if user's subscription is active."""
        return obj.is_subscription_active()
    is_subscription_active.short_description = 'Active'
    is_subscription_active.boolean = True

    # Custom admin actions
    actions = ['activate_users', 'deactivate_users', 'upgrade_to_pro', 'reset_quotas']

    def activate_users(self, request, queryset):
        """Activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated.')
    activate_users.short_description = 'Activate selected users'

    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'

    def upgrade_to_pro(self, request, queryset):
        """Upgrade users to Pro plan."""
        updated = queryset.update(subscription_plan='pro')
        self.message_user(request, f'{updated} users upgraded to Pro.')
    upgrade_to_pro.short_description = 'Upgrade to Pro plan'

    def reset_quotas(self, request, queryset):
        """Reset usage quotas for selected users."""
        for user in queryset:
            try:
                quota = user.usage_quota
                quota.reset_monthly_usage()
            except UsageQuota.DoesNotExist:
                pass
        self.message_user(request, 'Quotas reset for selected users.')
    reset_quotas.short_description = 'Reset monthly quotas'


class SocialPlatformAccountAdmin(admin.ModelAdmin):
    """
    Admin for social platform accounts.
    Shows connection status and platform info.
    """

    list_display = (
        'user_email',
        'platform_icon',
        'platform_user_id',
        'token_status',
        'expires_at',
        'created_at',
    )

    list_filter = (
        'platform',
        'is_active',
        'created_at',
    )

    search_fields = (
        'user__email',
        'user__username',
        'platform_user_id',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'access_token_encrypted',
        'refresh_token_encrypted',
        'created_at',
        'updated_at',
    )

    def user_email(self, obj):
        """Display user's email."""
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def platform_icon(self, obj):
        """Display platform with icon."""
        icons = {
            'linkedin': '🔗',
            'twitter': '🐦',
            'facebook': '📘',
            'instagram': '📸',
        }
        icon = icons.get(obj.platform, '📌')
        return format_html('{} {}', icon, obj.get_platform_display())
    platform_icon.short_description = 'Platform'

    def token_status(self, obj):
        """Show token expiry status."""
        if obj.expires_at is None:
            color = '#4caf50'  # Green - never expires
            text = 'No Expiry'
        elif obj.expires_at <= timezone.now():
            color = '#f44336'  # Red - expired
            text = 'Expired'
        else:
            color = '#ff9800'  # Orange - valid
            days_left = (obj.expires_at - timezone.now()).days
            text = f'{days_left} days left'
        return format_html(
            '<span style="color: {};">● {}</span>',
            color,
            text
        )
    token_status.short_description = 'Token Status'


class UsageQuotaAdmin(admin.ModelAdmin):
    """
    Admin for usage quotas.
    Monitor usage against limits.
    """

    list_display = (
        'user_email',
        'posts_used_display',
        'ai_used_display',
        'webhooks_used',
        'last_reset',
        'reset_link',
    )

    list_filter = (
        'last_reset',
    )

    search_fields = ('user__email', 'user__username')

    readonly_fields = (
        'last_reset',
        'posts_this_month',
        'ai_generations_this_month',
        'webhooks_triggered_this_month',
    )

    def user_email(self, obj):
        """Display user's email."""
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def posts_used_display(self, obj):
        """Show posts usage with progress bar."""
        limit = obj.get_limit('posts')
        used = obj.posts_this_month
        if limit == -1:
            return f'{used} / ∞'
        percent = min(100, (used / limit) * 100) if limit > 0 else 100
        color = '#4caf50' if percent < 70 else '#ff9800' if percent < 90 else '#f44336'
        return format_html(
            '<div style="width: 100px;">'
            '<div style="background-color: #e0e0e0; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; height: 8px;"></div>'
            '</div>'
            '<span style="font-size: 11px;">{}/{}</span>'
            '</div>',
            percent,
            color,
            used,
            limit
        )
    posts_used_display.short_description = 'Posts'

    def ai_used_display(self, obj):
        """Show AI usage with progress bar."""
        limit = obj.get_limit('ai_generations')
        used = obj.ai_generations_this_month
        if limit == -1:
            return f'{used} / ∞'
        percent = min(100, (used / limit) * 100) if limit > 0 else 100
        color = '#4caf50' if percent < 70 else '#ff9800' if percent < 90 else '#f44336'
        return format_html(
            '<div style="width: 100px;">'
            '<div style="background-color: #e0e0e0; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; height: 8px;"></div>'
            '</div>'
            '<span style="font-size: 11px;">{}/{}</span>'
            '</div>',
            percent,
            color,
            used,
            limit
        )
    ai_used_display.short_description = 'AI Generations'

    def webhooks_used(self, obj):
        """Show webhook usage."""
        limit = obj.get_limit('webhooks')
        used = obj.webhooks_triggered_this_month
        if limit == -1:
            return f'{used} / ∞'
        return f'{used} / {limit}'
    webhooks_used.short_description = 'Webhooks'

    def reset_link(self, obj):
        """Quick reset button."""
        return format_html(
            '<a href="?reset_quota=True&user_id={}" '
            'style="background-color: #4f46e5; color: white; padding: 4px 8px; '
            'border-radius: 4px; text-decoration: none; font-size: 12px;">Reset</a>',
            obj.user.id
        )
    reset_link.short_description = 'Actions'

    def get_actions(self, request):
        """Add reset action."""
        actions = super().get_actions(request)
        actions['reset_quotas'] = (
            self.reset_quotas,
            'reset_quotas',
            'Reset Monthly Quotas'
        )
        return actions

    def reset_quotas(self, request, queryset):
        """Reset quotas for selected users."""
        for quota in queryset:
            quota.reset_monthly_usage()
        self.message_user(request, 'Quotas reset successfully.')
    reset_quotas.short_description = 'Reset monthly quotas'
