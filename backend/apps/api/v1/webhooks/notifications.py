"""
Generic notification webhook endpoints for FastAPI.

Telegram receives provider-aware parsing today, while other platforms can
already store raw webhook events through the same endpoint shape.
"""

from datetime import datetime
from typing import Any
import uuid

import httpx
from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import api_settings
from apps.api.v1.tasks.post_task import consume_telegram_action
from shared.database import get_db
from shared.models.notifications import (
    NotificationConnection,
    NotificationConnectionRequest,
    NotificationWebhookEvent,
)
from shared.models.users import User
from shared.schemas.notifications import (
    NotificationConnectionResponse,
    NotificationWebhookEventResponse,
    NotificationWebhookReceiveResponse,
)


router = APIRouter(prefix="/webhooks", tags=["notification-webhooks"])


def _parse_telegram_action(callback_query: dict[str, Any]) -> tuple[str | None, str | None]:
    callback_data = (callback_query.get("data") or "").strip()
    if not callback_data:
        return None, None

    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "automation":
        return None, None

    action = parts[1].lower().strip()
    reference_id = parts[2].strip()

    if action not in {"confirm", "stop"} or not reference_id:
        return None, None

    return action, reference_id


async def _answer_telegram_callback(callback_query_id: str, action: str | None) -> None:
    token = api_settings.TELEGRAM_BOT_TOKEN
    if not token or not callback_query_id:
        return

    text = "Action received"
    if action == "confirm":
        text = "Automation confirmed"
    elif action == "stop":
        text = "Automation stop requested"

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{api_settings.TELEGRAM_BASE_URL}/bot{token}/answerCallbackQuery",
            json={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": False,
            },
        )


def _extract_telegram_context(payload: dict[str, Any]) -> dict[str, Any]:
    update_id = payload.get("update_id")
    message = payload.get("message") or {}
    callback_query = payload.get("callback_query") or {}
    action, action_reference = _parse_telegram_action(callback_query)

    if callback_query and not message:
        message = callback_query.get("message") or {}
        sender = callback_query.get("from") or {}
        event_type = "callback_query"
    else:
        sender = message.get("from") or {}
        event_type = "message" if message else "unknown"

    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    connect_reference_id = None

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            connect_reference_id = parts[1].strip() or None

    return {
        "event_type": event_type,
        "external_event_id": str(update_id or ""),
        "destination": str(chat.get("id", "") or ""),
        "external_user_id": str(sender.get("id", "") or ""),
        "display_name": " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")])).strip(),
        "metadata": {
            "telegram_username": sender.get("username", "") or "",
            "chat_type": chat.get("type", "private"),
            "message_text": text,
            "action": action or "",
            "action_reference": action_reference or "",
            "callback_query_id": callback_query.get("id", "") or "",
        },
        "connect_reference_id": connect_reference_id,
        "is_verified": bool(chat.get("id")),
        "action": action,
        "action_reference": action_reference,
    }


def _extract_generic_context(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    if platform == "telegram":
        return _extract_telegram_context(payload)

    external_event_id = payload.get("id") or payload.get("event_id") or payload.get("message_id") or ""
    destination = payload.get("destination") or payload.get("to") or payload.get("channel") or ""
    external_user_id = payload.get("user_id") or payload.get("external_user_id") or payload.get("from") or ""
    event_type = payload.get("event_type") or payload.get("event") or payload.get("type") or "unknown"

    return {
        "event_type": str(event_type),
        "external_event_id": str(external_event_id or ""),
        "destination": str(destination or ""),
        "external_user_id": str(external_user_id or ""),
        "display_name": str(payload.get("display_name") or payload.get("name") or ""),
        "metadata": {},
        "connect_reference_id": None,
        "is_verified": False,
        "action": None,
        "action_reference": None,
    }


async def _find_existing_connection(
    db: AsyncSession,
    platform: str,
    destination: str,
    external_user_id: str,
) -> NotificationConnection | None:
    if external_user_id:
        result = await db.execute(
            select(NotificationConnection).where(
                NotificationConnection.platform == platform,
                NotificationConnection.external_user_id == external_user_id,
            )
        )
        connection = result.scalar_one_or_none()
        if connection is not None:
            return connection

    if destination:
        result = await db.execute(
            select(NotificationConnection).where(
                NotificationConnection.platform == platform,
                NotificationConnection.destination == destination,
            )
        )
        return result.scalar_one_or_none()

    return None


async def _find_connection_request(
    db: AsyncSession,
    platform: str,
    reference_id: str | None,
) -> NotificationConnectionRequest | None:
    if platform != "telegram" or not reference_id:
        return None

    now = datetime.utcnow()
    result = await db.execute(
        select(NotificationConnectionRequest).where(
            NotificationConnectionRequest.platform == platform,
            NotificationConnectionRequest.reference_id == reference_id,
            NotificationConnectionRequest.is_active.is_(True),
            NotificationConnectionRequest.used_at.is_(None),
            NotificationConnectionRequest.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def _find_user(
    db: AsyncSession,
    platform: str,
    context: dict[str, Any],
) -> tuple[User | None, NotificationConnection | None, NotificationConnectionRequest | None]:
    connection_request = await _find_connection_request(db, platform, context.get("connect_reference_id"))
    if connection_request is not None:
        result = await db.execute(select(User).where(User.id == connection_request.user_id))
        return result.scalar_one_or_none(), None, connection_request

    connection = await _find_existing_connection(
        db,
        platform=platform,
        destination=context["destination"],
        external_user_id=context["external_user_id"],
    )
    if connection is None:
        return None, None, None

    result = await db.execute(select(User).where(User.id == connection.user_id))
    return result.scalar_one_or_none(), connection, None


async def _has_primary_connection(db: AsyncSession, user_id) -> bool:
    result = await db.execute(
        select(NotificationConnection.id).where(
            NotificationConnection.user_id == user_id,
            NotificationConnection.is_primary.is_(True),
            NotificationConnection.is_active.is_(True),
        )
    )
    return result.first() is not None


async def _upsert_connection(
    db: AsyncSession,
    platform: str,
    user: User,
    context: dict[str, Any],
    existing_connection: NotificationConnection | None,
) -> NotificationConnection:
    connection = existing_connection

    if connection is None:
        connection = await _find_existing_connection(
            db,
            platform=platform,
            destination=context["destination"],
            external_user_id=context["external_user_id"],
        )

    now = datetime.utcnow()

    if connection is None:
        connection = NotificationConnection(
            user_id=user.id,
            platform=platform,
            destination_type="chat" if platform == "telegram" else "custom",
            destination=context["destination"] or context["external_user_id"] or f"{platform}:{user.id}",
            created_at=now,
            updated_at=now,
            is_primary=not await _has_primary_connection(db, user.id),
        )
        db.add(connection)

    connection.user_id = user.id
    connection.platform = platform
    if context["destination"]:
        connection.destination = context["destination"]
    if context["external_user_id"]:
        connection.external_user_id = context["external_user_id"]
    connection.display_name = context["display_name"] or connection.display_name
    connection.metadata_json = {**(connection.metadata_json or {}), **context["metadata"]}
    connection.external_channel_id = context["destination"] or connection.external_channel_id
    connection.is_verified = bool(context["is_verified"] or connection.is_verified)
    connection.connected_at = connection.connected_at or now
    connection.last_interaction_at = now
    connection.last_inbound_event_id = context["external_event_id"]
    connection.updated_at = now

    await db.flush()
    return connection


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "notification-webhooks"}


@router.get("/{platform}/health")
async def platform_health_check(platform: str) -> dict[str, str]:
    return {"status": "healthy", "service": f"{platform}-webhook"}


@router.post("/{platform}/webhook", response_model=NotificationWebhookReceiveResponse)
async def receive_notification_webhook(
    platform: str,
    payload: dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
) -> NotificationWebhookReceiveResponse:
    platform = platform.lower().strip()
    context = _extract_generic_context(platform, payload)
    external_event_id = context["external_event_id"]
    action = context.get("action")
    action_reference = context.get("action_reference")

    existing_event = None
    if external_event_id:
        result = await db.execute(
            select(NotificationWebhookEvent).where(
                NotificationWebhookEvent.platform == platform,
                NotificationWebhookEvent.external_event_id == external_event_id,
            )
        )
        existing_event = result.scalar_one_or_none()

    if existing_event is not None:
        connection = None
        if existing_event.connection_id is not None:
            result = await db.execute(
                select(NotificationConnection).where(
                    NotificationConnection.id == existing_event.connection_id
                )
            )
            connection = result.scalar_one_or_none()

        return NotificationWebhookReceiveResponse(
            ok=True,
            event=NotificationWebhookEventResponse.model_validate(existing_event),
            connection=(
                NotificationConnectionResponse.model_validate(connection)
                if connection is not None
                else None
            ),
            linked_user_id=existing_event.user_id,
            action=existing_event.metadata_json.get("action") or None,
            action_reference=existing_event.metadata_json.get("action_reference") or None,
            detail="Duplicate webhook event ignored",
        )

    user, existing_connection, connection_request = await _find_user(db, platform, context)
    event = NotificationWebhookEvent(
        platform=platform,
        event_type=context["event_type"],
        direction="inbound",
        external_event_id=external_event_id,
        destination=context["destination"],
        external_user_id=context["external_user_id"],
        payload=payload,
        metadata_json=context["metadata"],
        processed=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(event)
    connection = None

    try:
        if user is not None:
            connection = await _upsert_connection(db, platform, user, context, existing_connection)
            event.user_id = user.id
            event.connection_id = connection.id
            if connection_request is not None:
                connection_request.used_at = datetime.utcnow()
                connection_request.is_active = False
                connection_request.updated_at = datetime.utcnow()

        event.processed = True
        event.processed_at = datetime.utcnow()
        event.error_message = ""
        event.updated_at = datetime.utcnow()

        await db.commit()
    except Exception as exc:
        await db.rollback()

        failed_event = NotificationWebhookEvent(
            platform=platform,
            event_type=context["event_type"],
            direction="inbound",
            external_event_id=external_event_id,
            destination=context["destination"],
            external_user_id=context["external_user_id"],
            payload=payload,
            metadata_json=context["metadata"],
            processed=False,
            error_message=str(exc),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(failed_event)
        await db.commit()
        await db.refresh(failed_event)

        return NotificationWebhookReceiveResponse(
            ok=False,
            event=NotificationWebhookEventResponse.model_validate(failed_event),
            connection=None,
            linked_user_id=None,
            action=action,
            action_reference=action_reference,
            detail="Webhook stored but connection update failed",
        )

    await db.refresh(event)
    if connection is not None:
        await db.refresh(connection)

    detail = "Webhook processed successfully"
    if platform == "telegram" and user is not None and action and action_reference:
        action_detail = await consume_telegram_action(
            db,
            user_id=user.id,
            action=action,
            reference_id=action_reference,
        )
        if action_detail:
            detail = action_detail

    if platform == "telegram" and context["metadata"].get("callback_query_id"):
        try:
            await _answer_telegram_callback(context["metadata"]["callback_query_id"], action)
        except httpx.HTTPError:
            pass

    return NotificationWebhookReceiveResponse(
        ok=True,
        event=NotificationWebhookEventResponse.model_validate(event),
        connection=(
            NotificationConnectionResponse.model_validate(connection)
            if connection is not None
            else None
        ),
        linked_user_id=user.id if user is not None else None,
        action=action,
        action_reference=action_reference,
        detail=detail,
    )
