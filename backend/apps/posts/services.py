"""
Services for LinkedIn post management.

Note: Core publishing and approval logic has been moved to tasks.py
for use with Celery background tasks. This module can be used for
non-async helper functions.
"""

from django.utils import timezone 

from apps.posts.models import ScheduledPost, PostStatus


def get_posts_for_user(user_id: str, status: str = None):
    """
    Get posts for a specific user, optionally filtered by status.
    
    Args:
        user_id: The user's UUID
        status: Optional PostStatus value to filter by
        
    Returns:
        QuerySet of ScheduledPost objects
    """
    queryset = ScheduledPost.objects.filter(author_id=user_id)
    
    if status:
        queryset = queryset.filter(status=status)
    
    return queryset.order_by('-created_at')


def get_upcoming_deadlines(user_id: str, hours: int = 24):
    """
    Get posts with approval deadlines within the specified time window.
    
    Args:
        user_id: The user's UUID
        hours: Number of hours to look ahead
        
    Returns:
        QuerySet of ScheduledPost objects
    """
    now = timezone.now()
    window_end = now + timezone.timedelta(hours=hours)
    
    return ScheduledPost.objects.filter(
        author_id=user_id,
        approval_deadline__range=[now, window_end],
        status__in=[PostStatus.DRAFT, PostStatus.SENT_FOR_APPROVAL],
    ).order_by('approval_deadline')
