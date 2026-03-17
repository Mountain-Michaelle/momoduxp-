"""
Celery beat tasks for scheduled operations.
Handles periodic tasks like quota reset and cleanup.
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(name="apps.scheduling.reset_monthly_quotas")
def reset_monthly_quotas() -> dict:
    """
    Reset monthly usage quotas for all users.

    This task should run on the 1st of each month at midnight.
    """
    from apps.accounts.models import UsageQuota

    try:
        # Get all usage quotas
        quotas = UsageQuota.objects.all()
        count = 0

        for quota in quotas:
            quota.reset_monthly_usage()
            count += 1

        logger.info(f"Reset monthly quotas for {count} users")
        return {"reset_count": count}

    except Exception as e:
        logger.error(f"Failed to reset monthly quotas: {e}")
        raise


@shared_task(name="apps.scheduling.cleanup_expired_tokens")
def cleanup_expired_tokens() -> dict:
    """
    Clean up expired social platform tokens.

    This task runs daily to remove or mark expired tokens.
    """
    from apps.accounts.models import SocialPlatformAccount

    try:
        expired = SocialPlatformAccount.objects.filter(
            expires_at__lt=timezone.now()
        )
        count = expired.count()

        # Instead of deleting, we could notify users
        # For now, just log
        logger.info(f"Found {count} expired social tokens")

        return {"expired_count": count}

    except Exception as e:
        logger.error(f"Failed to cleanup expired tokens: {e}")
        raise


@shared_task(name="apps.scheduling.check_subscription_expiry")
def check_subscription_expiry() -> dict:
    """
    Check for subscriptions expiring soon and notify users.

    This task runs weekly.
    """
    from apps.accounts.models import User, SubscriptionPlan

    try:
        expiring_soon = User.objects.filter(
            subscription_expires_at__isnull=False,
            subscription_expires_at__lte=timezone.now() + timedelta(days=7),
            subscription_expires_at__gt=timezone.now(),
        )

        count = expiring_soon.count()
        logger.info(f"Found {count} subscriptions expiring soon")

        # TODO: Send email notifications

        return {"expiring_count": count}

    except Exception as e:
        logger.error(f"Failed to check subscription expiry: {e}")
        raise


# Celery Beat Schedule Configuration
# Add to backend/backend/celery.py:
#
# beat_schedule = {
#     'reset-monthly-quotas': {
#         'task': 'apps.scheduling.reset_monthly_quotas',
#         'schedule': crontab(day=1, hour=0, minute=0),
#     },
#     'cleanup-expired-tokens': {
#         'task': 'apps.scheduling.cleanup_expired_tokens',
#         'schedule': crontab(hour=0, minute=0),  # Daily at midnight
#     },
#     'check-subscription-expiry': {
#         'task': 'apps.scheduling.check_subscription_expiry',
#         'schedule': crontab(day=7, hour=0, minute=0),  # Weekly
#     },
# }
