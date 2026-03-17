from django.db import models
from apps.core.models import BaseModel


class PostStatus(models.TextChoices):
    DRAFT = "draft"
    SENT_FOR_APPROVAL = "sent_for_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"

class ScheduledPost(BaseModel):
    author = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    account = models.ForeignKey('accounts.SocialPlatformAccount', on_delete=models.CASCADE)
    
    content = models.TextField()
    media_urls = models.JSONField(default=list, blank=True) # For images/videos
    
    status = models.CharField(
            max_length=32, choices=PostStatus.choices, default=PostStatus.DRAFT
        )   
     
    scheduled_for = models.DateTimeField()
    approval_deadline = models.DateTimeField() # 5hr mark for auto-post
    approved_at = models.DateTimeField(null=True, blank=True)

    # Metadata for tracking
    external_post_id = models.CharField(max_length=255, null=True, blank=True)
    platform_id = models.CharField(max_length=255, null=True, blank=True)
    error_log = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.account.platform} post by {self.author.username}"