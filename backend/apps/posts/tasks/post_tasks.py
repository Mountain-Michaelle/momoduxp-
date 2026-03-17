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
from celery.exceptions import Reject
from django.utils import timezone
from django.conf import settings
from decouple import config

from apps.integrations.linkedin.client import LinkedinClient
from apps.notifications.telegram.client import TelegramClient

from ..models import ScheduledPost, PostStatus
from shared.celery_utils import IdempotentTaskMixin

logger = logging.getLogger(__name__)


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
        post = ScheduledPost.objects.get(id=post_id)
    except ScheduledPost.DoesNotExist:
        logger.error(f"Post with ID {post_id} not found")
        return
    
    # Get Telegram credentials from environment
    telegram_token = config('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = config('TELEGRAM_APPROVAL_CHAT_ID')
    
    # Initialize Telegram client with environment credentials
    telegram = TelegramClient(
        bot_token=telegram_token,
        chat_id=telegram_chat_id,
    )
    
    try:
        # Send approval request (use synchronous method for Celery)
        telegram.send_approval_sync(
            f"Review LinkedIn Post:\n\n{post.content}",
            str(post.id),
        )
        
        # Update status
        post.status = PostStatus.SENT_FOR_APPROVAL
        post.save()
        
        logger.info(f"Sent post {post_id} for approval")
        
    except Exception as e:
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
