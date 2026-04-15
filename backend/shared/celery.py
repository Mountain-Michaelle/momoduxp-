# shared/celery.py

import os
# if os.environ.get("CELERY_WORKER_RUNNING"):
#     from gevent import monkey
#     monkey.patch_all()

import logging
from pathlib import Path
from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# ENV LOADER
# ------------------------------------------------------------------------------


def load_dotenv_once() -> None:
    if os.getenv("DOTENV_LOADED") == "1":
        return

    backend_dir = Path(__file__).resolve().parent.parent
    env_path = backend_dir / ".env"

    try:
        from dotenv import load_dotenv

        if env_path.exists():
            load_dotenv(env_path)
            logger.info("Loaded .env from %s", env_path)
    except ImportError:
        if env_path.exists():
            with env_path.open() as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        os.environ.setdefault(k, v)

    os.environ["DOTENV_LOADED"] = "1"


load_dotenv_once()


# ------------------------------------------------------------------------------
# DJANGO SETUP
# ------------------------------------------------------------------------------


def django_enabled() -> bool:
    return bool(os.getenv("DJANGO_SETTINGS_MODULE"))


def setup_django_once() -> None:
    if os.getenv("DJANGO_SETUP_DONE") == "1":
        return

    import django

    django.setup()

    # FIX: Import all SQLAlchemy models to ensure relationships are resolved
    # before any task tries to use them. Without this, the "User" relationship
    # in NotificationConnection fails to resolve because User model isn't loaded.
    from shared.models import users  # noqa
    from shared.models import notifications  # noqa
    from shared.models import posts  # noqa

    os.environ["DJANGO_SETUP_DONE"] = "1"
    logger.info("Django initialized for Celery")


# ------------------------------------------------------------------------------
# CELERY FACTORY
# ------------------------------------------------------------------------------


def create_celery_app() -> Celery:
    app = Celery("momodu")

    app.set_default()

    # IMPORTANT: Django must be setup BEFORE autodiscover to ensure models are loaded
    if django_enabled():
        setup_django_once()

    # Now discover tasks - models are ready
    app.autodiscover_tasks(
        [
            "apps.api.v1.tasks.post_task",
            "apps.webhooks.tasks",
        ]
    )

    if django_enabled():
        from django.conf import settings

        app.config_from_object("django.conf:settings", namespace="CELERY")

        app.conf.beat_schedule = {
            "approval-deadline-watcher": {
                "task": "apps.api.v1.tasks.post_task.approval_deadline_watcher",
                "schedule": 60.0,
                "options": {"queue": "default"},
            },
            "cleanup-failed-posts": {
                "task": "apps.api.v1.tasks.post_task.cleanup_failed_posts",
                "schedule": 3600.0,
                "options": {"queue": "slow"},
            },
            "reset-monthly-quotas": {
                "task": "apps.scheduling.reset_monthly_quotas",
                "schedule": crontab(day_of_month=1, hour=0, minute=0),
                "options": {"queue": "slow"},
            },
        }

    else:
        broker = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL"))
        backend = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL"))

        if not broker:
            raise RuntimeError("CELERY_BROKER_URL must be set")

        app.conf.broker_url = broker
        app.conf.result_backend = backend

    # Ensure broker_url is always set (for both Django and non-Django modes)
    if not app.conf.broker_url:
        app.conf.broker_url = (
            os.getenv("CELERY_BROKER_URL")
            or os.getenv("REDIS_URL")
            or "redis://localhost:6379/0"
        )

    # GLOBAL CONFIG
    app.conf.update(
        timezone="UTC",
        enable_utc=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=500,
        broker_pool_limit=10,
        broker_transport_options={
            "visibility_timeout": 3600,
            "socket_keepalive": True,
            "retry_on_timeout": True,
            "max_retries": 3,
        },
        broker_connection_retry_on_startup=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        task_soft_time_limit=270,
        task_time_limit=300,
        task_default_queue="default",
    )

    logger.info("Celery app initialized (django=%s)", django_enabled())
    return app


_celery_app = None


def get_celery_app():
    global _celery_app
    if _celery_app is None:
        _celery_app = create_celery_app()
    return _celery_app


celery_app = get_celery_app()
