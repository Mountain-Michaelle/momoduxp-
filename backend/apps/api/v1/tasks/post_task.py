import logging
import uuid
from datetime import datetime, timedelta
from functools import lru_cache

import requests
from celery import shared_task
from sqlalchemy import select, text, update

from apps.api.config import api_settings
from apps.integrations.linkedin.client import LinkedinClient
from shared.database import get_sync_session
from shared.models.notifications import NotificationConnection, NotificationDelivery
from shared.models.posts import PostStatus, ScheduledPost

logger = logging.getLogger(__name__)

SEND_FOR_APPROVAL_TASK = "apps.api.v1.tasks.post_task.send_for_approval"
PUBLISH_POST_TASK = "apps.api.v1.tasks.post_task.publish_post"
APPROVAL_DEADLINE_WATCHER_TASK = "apps.api.v1.tasks.post_task.approval_deadline_watcher"
CLEANUP_FAILED_POSTS_TASK = "apps.api.v1.tasks.post_task.cleanup_failed_posts"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.utcnow()


from cryptography.fernet import Fernet as _Fernet


@lru_cache(maxsize=1)
def _get_fernet() -> _Fernet:
    return _Fernet(api_settings.ENCRYPTION_KEY.encode())


def _approval_message(post: ScheduledPost) -> str:
    return f"LinkedIn post awaiting automation review.\n\n{post.content}"


def _decrypt_access_token(encrypted_token: str) -> str:
    return _get_fernet().decrypt(encrypted_token.encode()).decode()


def _get_celery_app():
    from shared.celery import get_celery_app

    return get_celery_app()


# ── DB helpers ────────────────────────────────────────────────────────────────


def _get_post(db, post_id: str) -> ScheduledPost | None:
    result = db.execute(
        select(ScheduledPost).where(
            ScheduledPost.id == uuid.UUID(post_id),
            ScheduledPost.is_active.is_(True),
        )
    )
    post = result.scalar_one_or_none()
    logger.info("DEBUG _get_post post_id=%s found=%s", post_id, post is not None)
    return post


def _get_active_telegram_connection(db, user_id) -> NotificationConnection | None:
    result = db.execute(
        select(NotificationConnection)
        .where(
            NotificationConnection.user_id == user_id,
            NotificationConnection.platform == "telegram",
            NotificationConnection.is_active.is_(True),
            NotificationConnection.is_verified.is_(True),
        )
        .order_by(
            NotificationConnection.is_primary.desc(),
            NotificationConnection.created_at.desc(),
        )
    )
    connection = result.scalars().first()
    logger.info("Telegram connection: %s", connection)
    return connection


def _load_linkedin_credentials(db, account_id) -> tuple[str, str]:
    result = db.execute(
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
        raise ValueError("Active LinkedIn account not found")
    return row["platform_user_id"], _decrypt_access_token(row["access_token_encrypted"])


# ── Telegram ──────────────────────────────────────────────────────────────────


def _send_telegram_message(
    chat_id: str, text: str, reply_markup: dict | None = None
) -> dict:
    url = f"{api_settings.TELEGRAM_BASE_URL}/bot{api_settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    logger.info("Sending Telegram message to chat_id=%s", chat_id)
    response = requests.post(url, json=payload, timeout=15.0)
    response.raise_for_status()
    result = response.json()
    logger.info("Telegram message sent successfully chat_id=%s", chat_id)
    return result


def _build_automation_keyboard(reference_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Confirm",
                    "callback_data": f"automation:confirm:{reference_id}",
                },
                {"text": "Stop", "callback_data": f"automation:stop:{reference_id}"},
            ]
        ]
    }


# ── Post state helpers ────────────────────────────────────────────────────────


def approve_post_record(
    db, post: ScheduledPost, *, trigger_publish: bool = True
) -> ScheduledPost:
    now = _utcnow()
    post.status = PostStatus.APPROVED.value
    post.approved_at = now
    post.error_log = ""
    post.updated_at = now
    db.commit()
    if trigger_publish:
        try:
            trigger_publish_post(str(post.id))
        except Exception:
            logger.exception(
                "Approval committed but failed to enqueue publish task post_id=%s — "
                "approval_deadline_watcher will recover it on its next run",
                post.id,
            )
    return post


async def approve_post_record_async(
    db: "AsyncSession",
    post: ScheduledPost,
    *,
    trigger_publish: bool = True,
) -> ScheduledPost:
    now = _utcnow()
    post.status = PostStatus.APPROVED.value
    post.approved_at = now
    post.error_log = ""
    post.updated_at = now
    await db.commit()
    await db.refresh(post)

    if trigger_publish:
        try:
            trigger_publish_post(str(post.id))
        except Exception:
            logger.exception(
                "Approval committed but failed to enqueue publish task "
                "post_id=%s — watcher will recover it",
                post.id,
            )
    return post


def return_post_to_draft(
    db, post: ScheduledPost, *, error_log: str = ""
) -> ScheduledPost:
    post.status = PostStatus.DRAFT.value
    post.approved_at = None
    post.error_log = error_log
    post.updated_at = _utcnow()
    db.commit()
    db.refresh(post)
    return post


def consume_telegram_action(
    db, *, user_id, action: str | None, reference_id: str | None
) -> str | None:
    if action not in {"confirm", "stop"} or not reference_id or user_id is None:
        return None

    try:
        post_uuid = uuid.UUID(reference_id)
    except ValueError:
        return "Telegram action ignored: invalid post reference"

    result = db.execute(
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
        if post.status == PostStatus.APPROVED.value:
            return "Telegram confirm ignored: post already approved"
        if post.status != PostStatus.SENT_FOR_APPROVAL.value:
            return "Telegram action ignored: post is not awaiting approval"
        approve_post_record(db, post, trigger_publish=True)
        return "Telegram approval consumed successfully"

    if post.status == PostStatus.PUBLISHED.value:
        return "Telegram stop ignored: post already published"

    if post.status not in {
        PostStatus.SENT_FOR_APPROVAL.value,
        PostStatus.APPROVED.value,
        PostStatus.DRAFT.value,
    }:
        return "Telegram stop ignored: post is not in an interruptible state"

    return_post_to_draft(db, post, error_log="")
    return "Telegram stop consumed successfully"


# ── Task implementations ──────────────────────────────────────────────────────


def _send_for_approval_sync(post_id: str) -> None:
    with get_sync_session() as db:
        logger.info("TASK EXECUTING send_for_approval started post_id=%s", post_id)

        post = _get_post(db, post_id)
        logger.info("DEBUG: post found=%s post_id=%s", post is not None, post_id)
        if post:
            logger.info(
                "DEBUG: post status=%s is_active=%s", post.status, post.is_active
            )
        # if not post:
        #     logger.error("Post not found post_id=%s", post_id)
        #     return

        if post.status not in [
            PostStatus.DRAFT.value,
            PostStatus.SENT_FOR_APPROVAL.value,
        ]:
            logger.info(
                "send_for_approval skipped invalid state=%s post_id=%s",
                post.status,
                post_id,
            )
            return

        connection = _get_active_telegram_connection(db, post.author_id)
        logger.info("DEBUG connection=%s", connection)

        if not connection or not connection.destination:
            logger.error(
                "No Telegram connection user_id=%s connection=%s",
                post.author_id,
                connection,
            )
            raise ValueError("No active Telegram connection")

        response = _send_telegram_message(
            chat_id=connection.destination,
            text=_approval_message(post),
            reply_markup=_build_automation_keyboard(str(post.id)),
        )

        message_id = str((response.get("result") or {}).get("message_id") or "")

        delivery = NotificationDelivery(
            user_id=post.author_id,
            connection_id=connection.id,
            platform="telegram",
            notification_type="post_approval",
            body=_approval_message(post),
            payload={"post_id": str(post.id)},
            metadata_json={"scheduled_post_id": str(post.id)},
            status="sent",
            provider_message_id=message_id,
            sent_at=_utcnow(),
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(delivery)

        post.status = PostStatus.SENT_FOR_APPROVAL.value
        post.updated_at = _utcnow()

        db.commit()
        logger.info(
            "send_for_approval committed post_id=%s message_id=%s", post.id, message_id
        )


def _publish_post_sync(post_id: str) -> None:
    with get_sync_session() as db:
        result = db.execute(
            update(ScheduledPost)
            .where(
                ScheduledPost.id == uuid.UUID(post_id),
                ScheduledPost.status == PostStatus.APPROVED.value,
            )
            .values(status=PostStatus.PUBLISHING.value)
            .returning(ScheduledPost)
        )
        post = result.scalar_one_or_none()
        if not post:
            logger.info(
                "publish_post skipped — post not in APPROVED state post_id=%s", post_id
            )
            return

        platform_user_id, access_token = _load_linkedin_credentials(db, post.account_id)

        client = LinkedinClient(access_token=access_token)
        author_urn = f"urn:li:person:{platform_user_id}"

        external_id = client.post_text_sync(author_urn, post.content)

        post.status = PostStatus.PUBLISHED.value
        post.external_post_id = external_id
        post.updated_at = _utcnow()
        db.commit()

        logger.info(
            "publish_post completed post_id=%s external_id=%s", post_id, external_id
        )


def _approval_deadline_watcher_sync() -> int:
    with get_sync_session() as db:
        result = db.execute(
            update(ScheduledPost)
            .where(
                ScheduledPost.approval_deadline <= _utcnow(),
                ScheduledPost.status.in_([PostStatus.SENT_FOR_APPROVAL.value]),
                ScheduledPost.is_active.is_(True),
            )
            .values(status=PostStatus.APPROVED.value, updated_at=_utcnow())
            .returning(ScheduledPost.id)
            .execution_options(synchronize_session=False)
        )
        post_ids = [str(row) for row in result.scalars().all()]

    for post_id in post_ids:
        try:
            trigger_publish_post(post_id)
        except Exception:
            logger.exception(
                "approval_deadline_watcher failed to enqueue publish task "
                "post_id=%s — will retry on next watcher tick",
                post_id,
            )

    if post_ids:
        logger.info(
            "approval_deadline_watcher triggered publish for %s posts", len(post_ids)
        )

    return len(post_ids)


def _cleanup_failed_posts_sync(older_than_hours: int) -> int:
    cutoff = _utcnow() - timedelta(hours=older_than_hours)

    with get_sync_session() as db:
        result = db.execute(
            update(ScheduledPost)
            .where(
                ScheduledPost.status == PostStatus.FAILED.value,
                ScheduledPost.updated_at <= cutoff,
                ScheduledPost.is_active.is_(True),
            )
            .values(is_active=False, updated_at=_utcnow())
            .returning(ScheduledPost.id)
            .execution_options(synchronize_session=False)
        )
        deactivated_ids = [str(row) for row in result.scalars().all()]

    if deactivated_ids:
        logger.info(
            "cleanup_failed_posts deactivated %s posts older than %s hours",
            len(deactivated_ids),
            older_than_hours,
        )

    return len(deactivated_ids)


# ── Trigger helpers (ALL use send_task to guarantee correct broker) ───────────


def trigger_send_for_approval(post_id: str) -> None:
    app = _get_celery_app()
    logger.info("DEBUG: Celery app broker_url=%s", app.conf.broker_url)
    result = app.send_task(SEND_FOR_APPROVAL_TASK, args=[post_id], queue="default")
    logger.info(
        "Enqueued send_for_approval post_id=%s task_id=%s broker=%s",
        post_id,
        result.id,
        app.conf.broker_url,
    )


def trigger_publish_post(post_id: str) -> None:
    app = _get_celery_app()
    app.send_task(PUBLISH_POST_TASK, args=[post_id], queue="default")
    logger.info(
        "Enqueued publish_post post_id=%s broker=%s", post_id, app.conf.broker_url
    )


def trigger_approval_deadline_watcher() -> None:
    try:
        app = _get_celery_app()
        app.send_task(APPROVAL_DEADLINE_WATCHER_TASK, queue="default")
        logger.info("Triggered approval_deadline_watcher task")
    except Exception as exc:
        logger.exception(
            "Failed to trigger approval_deadline_watcher task error=%s", exc
        )
        raise


# ── Celery task definitions ───────────────────────────────────────────────────


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    name=SEND_FOR_APPROVAL_TASK,
)
def send_for_approval(self, post_id: str) -> None:
    logger.info("TASK STARTED send_for_approval post_id=%s", post_id)
    _send_for_approval_sync(post_id)


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    name=PUBLISH_POST_TASK,
)
def publish_post(self, post_id: str) -> None:
    logger.info("TASK STARTED publish_post post_id=%s", post_id)
    _publish_post_sync(post_id)


@shared_task(bind=True, name=APPROVAL_DEADLINE_WATCHER_TASK)
def approval_deadline_watcher(self):
    logger.info("TASK STARTED approval_deadline_watcher")
    count = _approval_deadline_watcher_sync()
    return {"published_candidates": count}


@shared_task(bind=True, name=CLEANUP_FAILED_POSTS_TASK)
def cleanup_failed_posts(self, older_than_hours: int = 24) -> dict[str, int]:
    logger.info("TASK STARTED cleanup_failed_posts")
    count = _cleanup_failed_posts_sync(older_than_hours)
    return {"deactivated_count": count}
