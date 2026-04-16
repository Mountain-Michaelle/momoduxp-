from django.contrib.auth.models import AbstractUser
from apps.core.models import BaseModel
from django.db import models
from django.utils import timezone


# Subscription plan choices
class SubscriptionPlan(models.TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Pro"
    ENTERPRISE = "enterprise", "Enterprise"


class User(AbstractUser, BaseModel):
    """Custom user model with email as primary identifier."""

    email = models.EmailField(unique=True)
    subscription_plan = models.CharField(
        max_length=20, choices=SubscriptionPlan.choices, default=SubscriptionPlan.FREE
    )
    subscription_expires_at = models.DateTimeField(null=True, blank=True)

    def is_subscription_active(self) -> bool:
        """Check if user has active subscription."""
        if self.subscription_plan == SubscriptionPlan.FREE:
            return True  # Free tier is always active
        if self.subscription_expires_at is None:
            return False
        return self.subscription_expires_at > timezone.now()


class SocialPlatformAccount(BaseModel):
    """Social platform account credentials."""

    PLATFORM_CHOICES = [
        ("linkedin", "LinkedIn"),
        ("twitter", "Twitter"),
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="social_accounts"
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    platform_user_id = models.CharField(max_length=255)
    access_token_encrypted = models.TextField(help_text="Encrypted access token")
    refresh_token_encrypted = models.TextField(
        null=True, blank=True, help_text="Encrypted refresh token"
    )
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "platform", "platform_user_id")

    # Token encryption helpers
    def set_access_token(self, raw_token: str) -> None:
        """Encrypt and set access token."""
        from shared.utils import encrypt_token

        self.access_token_encrypted = encrypt_token(raw_token)

    def get_access_token(self) -> str:
        """Decrypt and get access token."""
        from shared.utils import decrypt_token

        return decrypt_token(self.access_token_encrypted)

    def set_refresh_token(self, raw_token: str) -> None:
        """Encrypt and set refresh token."""
        from shared.utils import encrypt_token

        self.refresh_token_encrypted = encrypt_token(raw_token)

    def get_refresh_token(self) -> str:
        """Decrypt and get refresh token."""
        from shared.utils import decrypt_token

        return decrypt_token(self.refresh_token_encrypted)

    def is_token_expired(self) -> bool:
        """Check if access token is expired."""
        if self.expires_at is None:
            return False
        return self.expires_at <= timezone.now()


class UsageQuota(BaseModel):
    """Usage quotas for subscription plans."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="usage_quota"
    )
    posts_this_month = models.IntegerField(default=0)
    ai_generations_this_month = models.IntegerField(default=0)
    webhooks_triggered_this_month = models.IntegerField(default=0)
    last_reset = models.DateTimeField(auto_now_add=True)

    PLAN_LIMITS = {
        "free": {"posts": 10, "ai_generations": 5, "webhooks": 100},
        "pro": {"posts": 100, "ai_generations": 50, "webhooks": 1000},
        "enterprise": {"posts": -1, "ai_generations": -1, "webhooks": -1},
    }

    def get_limit(self, resource: str) -> int:
        """Get limit for a resource."""
        limits = self.PLAN_LIMITS.get(self.user.subscription_plan, {})
        return limits.get(resource, 0)

    def can_create_post(self) -> bool:
        """Check if user can create more posts this month."""
        limit = self.get_limit("posts")
        if limit == -1:
            return True
        return self.posts_this_month < limit

    def can_use_ai(self) -> bool:
        """Check if user can use AI generation."""
        limit = self.get_limit("ai_generations")
        if limit == -1:
            return True
        return self.ai_generations_this_month < limit

    def increment_posts(self) -> None:
        """Increment post count."""
        self.posts_this_month += 1
        self.save(update_fields=["posts_this_month"])

    def increment_ai_generations(self) -> None:
        """Increment AI generation count."""
        self.ai_generations_this_month += 1
        self.save(update_fields=["ai_generations_this_month"])

    def reset_monthly_usage(self) -> None:
        """Reset monthly usage counters."""
        self.posts_this_month = 0
        self.ai_generations_this_month = 0
        self.webhooks_triggered_this_month = 0
        self.save()


class OAuthAccount(BaseModel):
    """
    OAuth provider account linking.
    Links users to external OAuth providers (Google, GitHub, etc.)
    """

    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("github", "GitHub"),
        ("facebook", "Facebook"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="oauth_accounts"
    )
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=255)
    access_token = models.TextField(default="")
    refresh_token = models.TextField(null=True, blank=True)
    id_token = models.TextField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.CharField(max_length=500, default="")
    extra_data = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("provider", "provider_user_id")
        indexes = [
            models.Index(fields=["user", "provider"]),
            models.Index(fields=["user", "provider", "is_active"]),
        ]

    def __str__(self):
        return f"{self.provider}:{self.user.email}"

    @property
    def is_token_expired(self) -> bool:
        """Check if access token is expired."""
        if not self.token_expires_at:
            return False
        return self.token_expires_at <= timezone.now()
