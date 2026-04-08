"""
Telegram notification routes for FastAPI.

Owns both Telegram connection-link generation and outbound message delivery.
"""

from datetime import datetime, timedelta
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import api_settings
from apps.api.v1.auth.dependencies import get_current_active_user
from apps.notifications.telegram.client import TelegramClient
from shared.database import get_db
from shared.models.notifications import (
    NotificationConnection,
    NotificationConnectionRequest,
    NotificationDelivery,
)
from shared.models.users import User
from shared.schemas.notifications import (
    NotificationConnectionResponse,
    NotificationDeliveryResponse,
    TelegramConnectLinkResponse,
    TelegramWebhookConfigResponse,
    TelegramNotificationSendRequest,
    TelegramNotificationSendResponse,
)


router = APIRouter(prefix="/notifications/telegram", tags=["telegram-notifications"])
CONNECT_TTL_MINUTES = 10


def _require_telegram_bot_token() -> str:
    token = api_settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TELEGRAM_BOT_TOKEN is not configured",
        )
    return token


def _telegram_bot_username() -> str:
    return api_settings.TELEGRAM_BOT_USERNAME.lstrip("@").strip()


def _generate_reference_id() -> str:
    return secrets.token_urlsafe(24)


def _webhook_url() -> str:
    base_url = (api_settings.PUBLIC_API_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PUBLIC_API_BASE_URL is not configured",
        )
    if not base_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram webhooks require an HTTPS PUBLIC_API_BASE_URL",
        )
    return f"{base_url}/api/v1/webhooks/telegram"


def _telegram_client() -> TelegramClient:
    return TelegramClient(
        bot_token=_require_telegram_bot_token(),
        base_url=api_settings.TELEGRAM_BASE_URL,
    )


async def _telegram_api_request(method: str, payload: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{api_settings.TELEGRAM_BASE_URL}/bot{_require_telegram_bot_token()}/{method}",
                json=payload or {},
            )
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telegram API request failed: {exc}",
        ) from exc


async def _get_target_connection(db: AsyncSession, user_id, connection_id=None) -> NotificationConnection:
    query = select(NotificationConnection).where(
        NotificationConnection.user_id == user_id,
        NotificationConnection.platform == "telegram",
        NotificationConnection.is_active.is_(True),
    )

    if connection_id is not None:
        query = query.where(NotificationConnection.id == connection_id)
    else:
        query = query.order_by(NotificationConnection.is_primary.desc(), NotificationConnection.created_at.desc())

    result = await db.execute(query)
    connection = result.scalars().first()

    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Telegram notification connection found for this user",
        )

    if not connection.destination:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram connection has no destination chat id",
        )

    return connection


@router.get("/connect-link", response_model=TelegramConnectLinkResponse)
async def create_telegram_connect_link(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TelegramConnectLinkResponse:
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=CONNECT_TTL_MINUTES)
    reference_id = _generate_reference_id()

    await db.execute(
        update(NotificationConnectionRequest)
        .where(
            NotificationConnectionRequest.user_id == current_user.id,
            NotificationConnectionRequest.platform == "telegram",
            NotificationConnectionRequest.used_at.is_(None),
            NotificationConnectionRequest.expires_at > now,
            NotificationConnectionRequest.is_active.is_(True),
        )
        .values(is_active=False, expires_at=now, updated_at=now)
    )

    db.add(
        NotificationConnectionRequest(
            user_id=current_user.id,
            platform="telegram",
            reference_id=reference_id,
            expires_at=expires_at,
            metadata_json={"bot_username": _telegram_bot_username()},
            created_at=now,
            updated_at=now,
        )
    )
    await db.commit()

    return TelegramConnectLinkResponse(
        ok=True,
        reference_id=reference_id,
        telegram_link=f"https://t.me/{_telegram_bot_username()}?start={reference_id}",
        expires_at=expires_at,
        detail="Telegram connect link generated successfully",
    )

@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "telegram-notifications"}


@router.post("/set-webhook", response_model=TelegramWebhookConfigResponse)
async def set_telegram_webhook() -> TelegramWebhookConfigResponse:
    webhook_url = _webhook_url()
    telegram_response = await _telegram_api_request("setWebhook", {"url": webhook_url})
    return TelegramWebhookConfigResponse(
        ok=bool(telegram_response.get("ok")),
        webhook_url=webhook_url,
        telegram_response=telegram_response,
        detail="Telegram webhook configured successfully",
    )


@router.get("/webhook-info", response_model=TelegramWebhookConfigResponse)
async def get_telegram_webhook_info() -> TelegramWebhookConfigResponse:
    telegram_response = await _telegram_api_request("getWebhookInfo")
    result = telegram_response.get("result", {}) if isinstance(telegram_response, dict) else {}
    return TelegramWebhookConfigResponse(
        ok=bool(telegram_response.get("ok")),
        webhook_url=result.get("url") or None,
        telegram_response=telegram_response,
        detail="Telegram webhook info fetched successfully",
    )


@router.delete("/webhook", response_model=TelegramWebhookConfigResponse)
async def delete_telegram_webhook() -> TelegramWebhookConfigResponse:
    telegram_response = await _telegram_api_request("deleteWebhook", {"drop_pending_updates": False})
    return TelegramWebhookConfigResponse(
        ok=bool(telegram_response.get("ok")),
        webhook_url=None,
        telegram_response=telegram_response,
        detail="Telegram webhook deleted successfully",
    )


@router.post("/send", response_model=TelegramNotificationSendResponse)
async def send_telegram_notification(
    request: TelegramNotificationSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TelegramNotificationSendResponse:
    connection = await _get_target_connection(db, current_user.id, request.connection_id)

    delivery = NotificationDelivery(
        user_id=current_user.id,
        connection_id=connection.id,
        platform="telegram",
        notification_type=request.notification_type,
        body=request.message,
        payload={
            "message": request.message,
            "reference_id": request.reference_id,
            "buttons": ["confirm", "stop"],
        },
        metadata_json=request.metadata,
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(delivery)
    await db.flush()

    try:
        telegram_response_data = await _telegram_client().send_message(
            chat_id=connection.destination,
            text=request.message,
            reply_markup=TelegramClient.build_automation_keyboard(request.reference_id),
        )
    except HTTPException as exc:
        delivery.status = "failed"
        delivery.failed_at = datetime.utcnow()
        delivery.error_message = exc.detail
        delivery.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(delivery)
        raise

    telegram_message_id = ""
    result = telegram_response_data.get("result", {}) if isinstance(telegram_response_data, dict) else {}
    if result.get("message_id") is not None:
        telegram_message_id = str(result["message_id"])

    delivery.status = "sent"
    delivery.provider_message_id = telegram_message_id
    delivery.sent_at = datetime.utcnow()
    delivery.error_message = ""
    delivery.updated_at = datetime.utcnow()

    connection.last_interaction_at = datetime.utcnow()
    connection.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(delivery)
    await db.refresh(connection)

    return TelegramNotificationSendResponse(
        ok=True,
        connection=NotificationConnectionResponse.model_validate(connection),
        delivery=NotificationDeliveryResponse.model_validate(delivery),
        telegram_message_id=telegram_message_id or None,
        detail="Telegram notification sent successfully",
    )
