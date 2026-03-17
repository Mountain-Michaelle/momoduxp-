"""
Webhook models for outgoing webhook endpoints.
DRY: Shared between Django and FastAPI.
"""

from django.db import models
from apps.core.models import BaseModel
import hmac
import hashlib


class WebhookEvent(BaseModel):
    """Webhook event types."""

    POST_CREATED = "post.created"
    POST_UPDATED = "post.updated"
    POST_PUBLISHED = "post.published"
    POST_FAILED = "post.failed"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"

    CHOICES = [
        (POST_CREATED, "Post Created"),
        (POST_UPDATED, "Post Updated"),
        (POST_PUBLISHED, "Post Published"),
        (POST_FAILED, "Post Failed"),
        (APPROVAL_APPROVED, "Approval Approved"),
        (APPROVAL_REJECTED, "Approval Rejected"),
    ]


class WebhookEndpoint(BaseModel):
    """User-defined webhook endpoints."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="webhook_endpoints"
    )
    url = models.URLField(max_length=500)
    secret = models.CharField(
        max_length=100,
        help_text="Secret for HMAC signature verification"
    )
    events = models.JSONField(
        default=list,
        help_text="List of event types to subscribe to"
    )
    is_active = models.BooleanField(default=True)
    failure_count = models.IntegerField(default=0)
    last_failure = models.DateTimeField(null=True, blank=True)

    def generate_signature(self, payload: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        return hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    def verify_signature(self, payload: str, signature: str) -> bool:
        """Verify HMAC signature from webhook response."""
        expected = self.generate_signature(payload)
        return hmac.compare_digest(expected, signature)


class WebhookDelivery(BaseModel):
    """Webhook delivery log."""

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="deliveries"
    )
    event = models.CharField(max_length=50, choices=WebhookEvent.CHOICES)
    payload = models.JSONField()
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    succeeded = models.BooleanField(default=False)
    duration_ms = models.IntegerField(null=True, blank=True)

    def mark_success(self, status_code: int, response_body: str, duration_ms: int):
        """Mark delivery as successful."""
        self.succeeded = True
        self.status_code = status_code
        self.response_body = response_body[:1000]  # Truncate
        self.duration_ms = duration_ms
        self.save()

    def mark_failed(self, status_code: int, error_message: str):
        """Mark delivery as failed."""
        self.succeeded = False
        self.status_code = status_code
        self.error_message = error_message
        self.endpoint.failure_count += 1
        self.endpoint.last_failure = timezone.now()
        self.endpoint.save()
        self.save()
