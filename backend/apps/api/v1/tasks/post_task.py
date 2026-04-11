import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from celery import shared_task
from cryptography.fernet import Fernet
from sqlalchemy import select, text

from apps.api.config import api_settings
from apps.integrations.linkedin.client import LinkedinClient
from apps.notifications.telegram.client import TelegramClient
from shared.database import async_session_maker
from shared.models.notifications import NotificationConnection, NotificationDelivery
from shared.models.posts import PostStatus, ScheduledPost

logger = logging.getLogger(__name__)

SEND_FOR_APPROVAL_TASK = "apps.api.v1.tasks.post_task.send_for_approval"
PUBLISH_POST_TASK = "apps.api.v1.tasks.post_task.publish_post"
APPROVAL_DEADLINE_WATCHER_TASK = "apps.api.v1.tasks.post_task.approval_deadline_watcher"
CLEANUP_FAILED_POSTS_TASK = "apps.api.v1.tasks.post_task.cleanup_failed_posts"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _get_celery_app():
    from shared.celery import get_celery_app

    return get_celery_app()


def _approval_message(post: ScheduledPost) -> str:
    return (
        "LinkedIn post awaiting automation review.\n\n"
        f"{post.content}"
    )


def _telegram_keyboard_reference(post_id: uuid.UUID) -> str:
    return str(post_id)


def _decrypt_access_token(encrypted_token: str) -> str:
    return Fernet(api_settings.ENCRYPTION_KEY.encode()).decrypt(encrypted_token.encode()).decode()


async def _get_post(db, post_id: str) -> ScheduledPost | None:
    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == uuid.UUID(post_id),
            ScheduledPost.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_active_telegram_connection(db, user_id) -> NotificationConnection | None:
    result = await db.execute(
        select(NotificationConnection)
        .where(
            NotificationConnection.user_id == user_id,
            NotificationConnection.platform == "telegram",
            NotificationConnection.is_active.is_(True),
            NotificationConnection.is_verified.is_(True),
        )
        .order_by(NotificationConnection.is_primary.desc(), NotificationConnection.created_at.desc())
    )
    return result.scalars().first()


async def _load_linkedin_credentials(db, account_id) -> tuple[str, str]:
    result = await db.execute(
        text(
            """
            SELECT platform_user_id, access_token_encrypted
            FROM accounts_socialplatformaccount
            WHERE id = :account_id AND is_active = TRUE
            """
        ),
        {"account_id": account_id},
    )
    row = result.mappings().first()
    if row is None:
        raise ValueError("Active LinkedIn account not found for post")
    return row["platform_user_id"], _decrypt_access_token(row["access_token_encrypted"])


async def approve_post_record(db, post: ScheduledPost, *, trigger_publish: bool = True) -> ScheduledPost:
    now = _utcnow()
    post.status = PostStatus.APPROVED.value
    post.approved_at = now
    post.error_log = ""
    post.updated_at = now
    await db.commit()
    await db.refresh(post)

    if trigger_publish:
        trigger_publish_post(str(post.id))

    return post


async def return_post_to_draft(db, post: ScheduledPost, *, error_log: str = "") -> ScheduledPost:
    post.status = PostStatus.DRAFT.value
    post.approved_at = None
    post.error_log = error_log
    post.updated_at = _utcnow()
    await db.commit()
    await db.refresh(post)
    return post


async def consume_telegram_action(
    db,
    *,
    user_id,
    action: str | None,
    reference_id: str | None,
) -> str | None:
    if action not in {"confirm", "stop"} or not reference_id or user_id is None:
        return None

    try:
        post_uuid = uuid.UUID(reference_id)
    except ValueError:
        return "Telegram action ignored: invalid post reference"

    result = await db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == post_uuid,
            ScheduledPost.author_id == user_id,
            ScheduledPost.is_active.is_(True),
        )
    )
    post = result.scalar_one_or_none()

    if post is None:
        return "Telegram action ignored: post not found"

    if action == "confirm":
        if post.status not in {PostStatus.SENT_FOR_APPROVAL.value, PostStatus.APPROVED.value}:
            return "Telegram action ignored: post is not awaiting approval"
        await approve_post_record(db, post, trigger_publish=True)
        return "Telegram approval consumed successfully"

    if post.status == PostStatus.PUBLISHED.value:
        return "Telegram stop ignored: post already published"

    if post.status not in {PostStatus.SENT_FOR_APPROVAL.value, PostStatus.APPROVED.value, PostStatus.DRAFT.value}:
        return "Telegram stop ignored: post is not in an interruptible state"

    await return_post_to_draft(db, post, error_log="")
    return "Telegram stop consumed successfully"


async def _send_for_approval_async(post_id: str) -> None:
    async with async_session_maker() as db:
        post = await _get_post(db, post_id)
        if post is None:
            logger.error("Post with ID %s not found", post_id)
            return

        connection = await _get_active_telegram_connection(db, post.author_id)
        if connection is None or not connection.destination:
            post.error_log = "User does not have an active Telegram notification connection"
            post.updated_at = _utcnow()
            await db.commit()
            raise ValueError(post.error_log)

        delivery = NotificationDelivery(
            user_id=post.author_id,
            connection_id=connection.id,
            platform="telegram",
            notification_type="post_approval",
            body=_approval_message(post),
            payload={
                "post_id": str(post.id),
                "buttons": ["confirm", "stop"],
            },
            metadata_json={"scheduled_post_id": str(post.id)},
            status="pending",
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(delivery)
        await db.flush()

        client = TelegramClient(
            bot_token=api_settings.TELEGRAM_BOT_TOKEN,
            base_url=api_settings.TELEGRAM_BASE_URL,
        )

        try:
            response = await client.send_message(
                chat_id=connection.destination,
                text=_approval_message(post),
                reply_markup=TelegramClient.build_automation_keyboard(
                    _telegram_keyboard_reference(post.id)
                ),
            )
        except Exception as exc:
            delivery.status = "failed"
            delivery.failed_at = _utcnow()
            delivery.error_message = str(exc)
            delivery.updated_at = _utcnow()
            post.error_log = f"{type(exc).__name__}: {exc}"
            post.updated_at = _utcnow()
            await db.commit()
            logger.error("Failed to send post %s for approval: %s", post_id, exc)
            raise

        message_id = str((response.get("result") or {}).get("message_id") or "")
        delivery.status = "sent"
        delivery.provider_message_id = message_id
        delivery.sent_at = _utcnow()
        delivery.error_message = ""
        delivery.updated_at = _utcnow()

        post.status = PostStatus.SENT_FOR_APPROVAL.value
        post.error_log = ""
        post.updated_at = _utcnow()

        connection.last_interaction_at = _utcnow()
        connection.updated_at = _utcnow()

        await db.commit()
        logger.info("Sent post %s for approval", post_id)


async def _publish_post_async(post_id: str) -> None:
    async with async_session_maker() as db:
        post = await _get_post(db, post_id)
        if post is None:
            logger.error("Post with ID %s not found", post_id)
            return

        if post.status == PostStatus.PUBLISHED.value:
            logger.info("Post %s already published, skipping", post_id)
            return

        try:
            platform_user_id, access_token = await _load_linkedin_credentials(db, post.account_id)
            linkedin_client = LinkedinClient(access_token=access_token)
            author_urn = f"urn:li:person:{platform_user_id}"
            external_post_id = await asyncio.to_thread(
                linkedin_client.post_text_sync,
                author_urn,
                post.content,
            )

            post.status = PostStatus.PUBLISHED.value
            post.external_post_id = external_post_id
            post.approved_at = post.approved_at or _utcnow()
            post.error_log = ""
            post.updated_at = _utcnow()
            await db.commit()
            logger.info("Successfully published post %s", post_id)
        except Exception as exc:
            post.status = PostStatus.FAILED.value
            post.error_log = f"{type(exc).__name__}: {exc}"
            post.updated_at = _utcnow()
            await db.commit()
            logger.error("Failed to publish post %s: %s", post_id, exc)
            raise


async def _approval_deadline_watcher_async() -> int:
    async with async_session_maker() as db:
        result = await db.execute(
            select(ScheduledPost.id).where(
                ScheduledPost.approval_deadline <= _utcnow(),
                ScheduledPost.status.in_(
                    [PostStatus.SENT_FOR_APPROVAL.value, PostStatus.DRAFT.value]
                ),
                ScheduledPost.is_active.is_(True),
            )
        )
        post_ids = [str(post_id) for post_id in result.scalars().all()]

    for post_id in post_ids:
        trigger_publish_post(post_id)

    if post_ids:
        logger.info(
            "Approval deadline watcher triggered publish for %s posts",
            len(post_ids),
        )

    return len(post_ids)


async def _cleanup_failed_posts_async(older_than_hours: int) -> int:
    cutoff = _utcnow() - timedelta(hours=older_than_hours)
    async with async_session_maker() as db:
        result = await db.execute(
            select(ScheduledPost.id).where(
                ScheduledPost.status == PostStatus.FAILED.value,
                ScheduledPost.updated_at <= cutoff,
                ScheduledPost.is_active.is_(True),
            )
        )
        post_ids = [str(post_id) for post_id in result.scalars().all()]

    if post_ids:
        logger.info(
            "Found %s failed posts older than %s hours",
            len(post_ids),
            older_than_hours,
        )

    return len(post_ids)


def trigger_send_for_approval(post_id: str) -> None:
    try:
        _get_celery_app().send_task(SEND_FOR_APPROVAL_TASK, args=[post_id], queue="fast")
        logger.info("Triggered send_for_approval task for post %s", post_id)
    except Exception as exc:
        logger.error("Failed to trigger send_for_approval task: %s", exc)


def trigger_publish_post(post_id: str) -> None:
    try:
        _get_celery_app().send_task(PUBLISH_POST_TASK, args=[post_id], queue="default")
        logger.info("Triggered publish_post task for post %s", post_id)
    except Exception as exc:
        logger.error("Failed to trigger publish_post task: %s", exc)


def trigger_approval_deadline_watcher() -> None:
    try:
        _get_celery_app().send_task(APPROVAL_DEADLINE_WATCHER_TASK, queue="default")
        logger.info("Triggered approval_deadline_watcher task")
    except Exception as exc:
        logger.error("Failed to trigger approval_deadline_watcher task: %s", exc)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    name=SEND_FOR_APPROVAL_TASK,
)
def send_for_approval(self, post_id: str) -> None:
    asyncio.run(_send_for_approval_async(post_id))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    name=PUBLISH_POST_TASK,
)
def publish_post(self, post_id: str) -> None:
    asyncio.run(_publish_post_async(post_id))


@shared_task(bind=True, name=APPROVAL_DEADLINE_WATCHER_TASK)
def approval_deadline_watcher(self) -> dict[str, int]:
    count = asyncio.run(_approval_deadline_watcher_async())
    return {"published_candidates": count}


@shared_task(bind=True, name=CLEANUP_FAILED_POSTS_TASK)
def cleanup_failed_posts(self, older_than_hours: int = 24) -> dict[str, int]:
    count = asyncio.run(_cleanup_failed_posts_async(older_than_hours))
    return {"failed_posts_count": count}
