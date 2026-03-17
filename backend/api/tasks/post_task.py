

import logging

logger = logging.getLogger(__name__)

def trigger_send_for_approval(post_id: str) -> None:
    """
   Args:
        post_id: UUID string of the ScheduledPost
    """
    try:
        # Import here to avoid circular imports and startup issues
        from shared.celery import celery_app
        celery_app.send_task(
            'apps.posts.tasks.post_tasks.send_for_approval',
            args=[post_id],
            queue='fast'
        )
        logger.info(f"Triggered send_for_approval task for post {post_id}")
    except Exception as e:
        logger.error(f"Failed to trigger send_for_approval task: {e}")


def trigger_publish_post(post_id: str) -> None:
    """
    Trigger Celery task to publish post to LinkedIn.
    
    Args:
        post_id: UUID string of the ScheduledPost
    """
    try:
        from shared.celery import celery_app
        celery_app.send_task(
            'apps.posts.tasks.post_tasks.publish_post',
            args=[post_id],
            queue='default'
        )
        logger.info(f"Triggered publish_post task for post {post_id}")
    except Exception as e:
        logger.error(f"Failed to trigger publish_post task: {e}")

