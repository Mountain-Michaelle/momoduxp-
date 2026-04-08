"""
Celery tasks for LinkedIn post scheduling and publishing.

This module contains background tasks for:
- Publishing posts to LinkedIn
- Sending posts for approval
- Auto-publishing posts past their approval deadline
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.integrations.linkedin.client import LinkedinClient
from apps.notifications.models import NotificationConnection, NotificationDelivery
from apps.notifications.telegram.client import TelegramClient

from ..models import ScheduledPost, PostStatus

logger = logging.getLogger(__name__)


def _get_active_telegram_connection(user_id):
    return (
        NotificationConnection.objects.filter(
            user_id=user_id,
            platform="telegram",
            is_active=True,
            is_verified=True,
        )
        .order_by("-is_primary", "-created_at")
        .first()
    )


def _approval_message(post: ScheduledPost) -> str:
    return (
        "LinkedIn post awaiting automation review.\n\n"
        f"{post.content}"
    )


def _send_telegram_approval(post: ScheduledPost) -> None:
    connection = _get_active_telegram_connection(post.author_id)
    if connection is None or not connection.destination:
        raise ValueError("User does not have an active Telegram notification connection")

    delivery = NotificationDelivery.objects.create(
        user_id=post.author_id,
        connection=connection,
        platform="telegram",
        notification_type="post_approval",
        body=_approval_message(post),
        payload={
            "post_id": str(post.id),
            "buttons": ["confirm", "stop"],
        },
        metadata={
            "scheduled_post_id": str(post.id),
        },
    )

    client = TelegramClient()

    try:
        response = client.send_message_sync(
            chat_id=connection.destination,
            text=_approval_message(post),
            reply_markup=TelegramClient.build_automation_keyboard(str(post.id)),
        )
    except Exception as exc:
        delivery.mark_failed(str(exc))
        raise

    message_id = str((response.get("result") or {}).get("message_id") or "")
    delivery.mark_sent(message_id)

    connection.last_interaction_at = timezone.now()
    connection.last_inbound_event_id = connection.last_inbound_event_id or ""
    connection.save(update_fields=["last_interaction_at", "updated_at"])


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={'max_retries': 3},
    name='apps.posts.tasks.publish_post'
)
def publish_post(self, post_id: str) -> None:

    try:
        # Fetch the post inside the task
        post = ScheduledPost.objects.select_related('account').get(id=post_id)
    except ScheduledPost.DoesNotExist:
        logger.error(f"Post with ID {post_id} not found")
        return
    
    # Idempotency check
    if post.status == PostStatus.PUBLISHED:
        logger.info(f"Post {post_id} already published, skipping...")
        return
    
    try:
        # Initialize LinkedIn client with account's access token
        linkedin_client = LinkedinClient(access_token=post.account.access_token)
        
        # Use account's platform_user_id for author_urn
        author_urn = f"urn:li:person:{post.account.platform_user_id}"
        
        # Publish the post (use synchronous method for Celery)
        external_post_id = linkedin_client.post_text_sync(
            author_urn=author_urn,
            text=post.content,
        )
        
        # Update post status
        post.status = PostStatus.PUBLISHED
        post.external_post_id = external_post_id
        post.approved_at = timezone.now()
        post.save()
        
        logger.info(f"Successfully published post {post_id}, external ID: {external_post_id}")
        
    except Exception as e:
        # Update status to FAILED on error
        post.status = PostStatus.FAILED
        post.error_log = f"{type(e).__name__}: {str(e)}"
        post.save()
        
        logger.error(f"Failed to publish post {post_id}: {e}")
        raise  # Re-raise for Celery retry mechanism


@shared_task(
    bind=True,
    name='apps.posts.tasks.send_for_approval'
)
def send_for_approval(self, post_id: str) -> None:
    
    """
    Send a post for approval via Telegram.
    
    This task fetches the post by ID and sends it to a Telegram channel
    for review before publishing.
    
    Args:
        post_id: UUID string of the ScheduledPost to send for approval
        
    Returns:
        None
        
    Raises:
        ScheduledPost.DoesNotExist: If post with given ID doesn't exist
    """
    try:
        post = ScheduledPost.objects.select_related("author").get(id=post_id)
    except ScheduledPost.DoesNotExist:
        logger.error(f"Post with ID {post_id} not found")
        return

    try:
        _send_telegram_approval(post)
        post.status = PostStatus.SENT_FOR_APPROVAL
        post.error_log = ""
        post.save(update_fields=["status", "error_log", "updated_at"])
        logger.info(f"Sent post {post_id} for approval")
    except Exception as e:
        post.error_log = f"{type(e).__name__}: {str(e)}"
        post.save(update_fields=["error_log", "updated_at"])
        logger.error(f"Failed to send post {post_id} for approval: {e}")
        raise


@shared_task(
    bind=True,
    name='apps.posts.tasks.approval_deadline_watcher'
)
def approval_deadline_watcher(self) -> None:
    """
    Periodic task to check for posts that need auto-publishing.
    
    This task runs every minute (configured in Celery beat) and checks
    for posts that:
    1. Have passed their approval deadline
    2. Are in SENT_FOR_APPROVAL or DRAFT status
    3. Have not been published yet
    
    For eligible posts, it triggers the publish_post task.
    
    Returns:
        None
    """
    now = timezone.now()
    
    # Find posts eligible for auto-publishing
    eligible_posts = ScheduledPost.objects.filter(
        approval_deadline__lte=now,
        status__in=[PostStatus.SENT_FOR_APPROVAL, PostStatus.DRAFT],
    ).exclude(
        status=PostStatus.PUBLISHED
    )
    
    count = 0
    for post in eligible_posts:
        # Dispatch publish_post task for each eligible post
        publish_post.delay(str(post.id))
        count += 1
    
    if count > 0:
        logger.info(f"Approval deadline watcher: triggered publish for {count} posts")


@shared_task(
    bind=True,
    name='apps.posts.tasks.cleanup_failed_posts'
)
def cleanup_failed_posts(self, older_than_hours: int = 24) -> None:
    """
    Cleanup task to handle failed posts.
    
    This task identifies posts that have been in FAILED status
    for a specified period and can be used for:
    - Notifying users of failed posts
    - Resetting status for retry
    - Archiving failed posts
    
    Args:
        older_than_hours: Consider posts failed longer than this many hours
        
    Returns:
        None
    """
    cutoff = timezone.now() - timedelta(hours=older_than_hours)
    
    failed_posts = ScheduledPost.objects.filter(
        status=PostStatus.FAILED,
        updated_at__lte=cutoff,
    )
    
    count = failed_posts.count()
    
    if count > 0:
        logger.info(f"Found {count} failed posts older than {older_than_hours} hours")
        # Future: Add notification/archival logic here
    
    return {"failed_posts_count": count}
