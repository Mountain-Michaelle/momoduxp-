"""
Webhook service for sending outgoing webhooks asynchronously.
DRY: Shared service for webhook operations.
"""

import asyncio
import httpx
import json
import logging
import time
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for sending webhooks to configured endpoints."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def send_webhook(
        self,
        url: str,
        event: str,
        payload: dict,
        secret: Optional[str] = None
    ) -> tuple[bool, int, str, int]:
        """
        Send a webhook to the specified URL.

        Args:
            url: Webhook endpoint URL
            event: Event type
            payload: Data to send
            secret: Secret for HMAC signature

        Returns:
            Tuple of (success, status_code, response_body, duration_ms)
        """
        import hmac
        import hashlib

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event,
            "X-Webhook-Timestamp": datetime.utcnow().isoformat(),
        }

        if secret:
            payload_str = json.dumps(payload, default=str)
            signature = hmac.new(
                secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                duration_ms = int((time.time() - start_time) * 1000)
                return True, res.status_code, res.text[:1000], duration_ms

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Webhook timeout for {url}: {event}")
            return False, 408, "Request timeout", duration_ms

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Webhook HTTP error for {url}: {e.response.status_code}")
            return False, e.response.status_code, str(e), duration_ms

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Webhook error for {url}: {e}")
            return False, 500, str(e), duration_ms

    async def send_webhooks_batch(
        self,
        endpoints: list[tuple[str, str, Optional[str]]],
        event: str,
        payload: dict
    ) -> list[dict]:
        """
        Send webhooks to multiple endpoints concurrently.

        Args:
            endpoints: List of (url, secret) tuples
            event: Event type
            payload: Data to send

        Returns:
            List of result dictionaries
        """
        tasks = [
            self.send_webhook(url, event, payload, secret)
            for url, secret in endpoints
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            {
                "url": url,
                "success": not isinstance(result, Exception) and result[0],
                "status_code": result[1] if not isinstance(result, Exception) else None,
                "duration_ms": result[3] if not isinstance(result, Exception) else None,
            }
            for (url, _), result in zip(endpoints, results)
        ]


# Singleton instance
webhook_service = WebhookService()


# Convenience functions for common webhook events
async def webhook_post_created(post_id: str, post_data: dict, endpoints: list):
    """Send post.created webhook."""
    payload = {
        "event": "post.created",
        "data": {
            "id": post_id,
            "content": post_data.get("content"),
            "scheduled_for": post_data.get("scheduled_for"),
        }
    }
    return await webhook_service.send_webhooks_batch(endpoints, "post.created", payload)


async def webhook_post_published(post_id: str, external_id: str, endpoints: list):
    """Send post.published webhook."""
    payload = {
        "event": "post.published",
        "data": {
            "id": post_id,
            "external_id": external_id,
            "published_at": datetime.utcnow().isoformat(),
        }
    }
    return await webhook_service.send_webhooks_batch(endpoints, "post.published", payload)


async def webhook_post_failed(post_id: str, error: str, endpoints: list):
    """Send post.failed webhook."""
    payload = {
        "event": "post.failed",
        "data": {
            "id": post_id,
            "error": error,
            "failed_at": datetime.utcnow().isoformat(),
        }
    }
    return await webhook_service.send_webhooks_batch(endpoints, "post.failed", payload)
