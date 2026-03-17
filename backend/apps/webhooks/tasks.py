"""
Celery tasks for webhook delivery.
Handles async webhook sending with retry logic.
"""

import logging
from celery import shared_task
from celery.exceptions import Reject

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="apps.webhooks.send_webhook",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_webhook(self, webhook_id: str) -> dict:
    """
    Send a webhook to an endpoint.

    Args:
        webhook_id: The webhook delivery record ID

    Returns:
        Dict with success status and details
    """
    from apps.webhooks.models import WebhookDelivery, WebhookEndpoint
    from apps.webhooks.service import webhook_service

    try:
        delivery = WebhookDelivery.objects.select_related("endpoint").get(id=webhook_id)
        endpoint = delivery.endpoint

        # Skip if endpoint is inactive
        if not endpoint.is_active:
            logger.info(f"Skipping webhook {webhook_id}: endpoint inactive")
            return {"success": False, "reason": "endpoint_inactive"}

        # Send webhook
        success, status_code, response_body, duration_ms = webhook_service.send_webhook(
            url=endpoint.url,
            event=delivery.event,
            payload=delivery.payload,
            secret=endpoint.secret,
        )

        if success:
            delivery.mark_success(status_code, response_body, duration_ms)
            logger.info(f"Webhook {webhook_id} sent successfully")
        else:
            delivery.mark_failed(status_code, response_body)
            logger.warning(f"Webhook {webhook_id} failed: {status_code}")

        return {"success": success, "webhook_id": webhook_id}

    except WebhookDelivery.DoesNotExist:
        logger.error(f"Webhook delivery {webhook_id} not found")
        return {"success": False, "reason": "not_found"}

    except Exception as e:
        logger.error(f"Webhook {webhook_id} error: {e}")
        raise Reject(reason=str(e))


@shared_task(name="apps.webhooks.retry_failed_webhooks")
def retry_failed_webhooks(hours: int = 24) -> dict:
    """
    Retry failed webhook deliveries.

    Args:
        hours: Retry webhooks that failed within this many hours

    Returns:
        Dict with count of retried webhooks
    """
    from django.utils import timezone
    from datetime import timedelta
    from apps.webhooks.models import WebhookDelivery

    cutoff = timezone.now() - timedelta(hours=hours)

    failed = WebhookDelivery.objects.filter(
        succeeded=False,
        endpoint__is_active=True,
        created_at__gte=cutoff,
    ).order_by("created_at")[:100]  # Limit to 100 at a time

    count = 0
    for delivery in failed:
        send_webhook.delay(str(delivery.id))
        count += 1

    logger.info(f"Queued {count} failed webhooks for retry")
    return {"retried_count": count}


@shared_task(name="apps.webhooks.cleanup_old_deliveries")
def cleanup_old_deliveries(days: int = 30) -> dict:
    """
    Delete old webhook delivery records.

    Args:
        days: Delete records older than this many days

    Returns:
        Dict with count of deleted records
    """
    from django.utils import timezone
    from datetime import timedelta
    from apps.webhooks.models import WebhookDelivery

    cutoff = timezone.now() - timedelta(days=days)

    deleted, _ = WebhookDelivery.objects.filter(created_at__lt=cutoff).delete()

    logger.info(f"Cleaned up {deleted} old webhook deliveries")
    return {"deleted_count": deleted}
