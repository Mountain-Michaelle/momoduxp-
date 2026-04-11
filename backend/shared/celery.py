"""
Shared Celery configuration (Django + FastAPI safe)

Design goals:
- Safe lazy initialization
- Django loaded only when required
- Worker-safe (no duplicate setup)
- Production-grade defaults
- Predictable behavior in multi-worker environments
"""

import os
import logging
from pathlib import Path
from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Environment loading (safe, idempotent)
# ------------------------------------------------------------------------------

def load_dotenv_once() -> None:
    """Load .env once, safely."""
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
# Django helpers
# ------------------------------------------------------------------------------

def django_enabled() -> bool:
    return bool(os.getenv("DJANGO_SETTINGS_MODULE"))


def setup_django_once() -> None:
    """Ensure django.setup() is called exactly once."""
    if os.getenv("DJANGO_SETUP_DONE") == "1":
        return

    import django
    django.setup()
    os.environ["DJANGO_SETUP_DONE"] = "1"
    logger.info("Django initialized for Celery")


# ------------------------------------------------------------------------------
# Celery factory
# ------------------------------------------------------------------------------

def create_celery_app() -> Celery:
    app = Celery("momodu")

    # ---------------------------
    # Django-backed workers
    # ---------------------------
    if django_enabled():
        setup_django_once()

        from django.conf import settings

        app.config_from_object("django.conf:settings", namespace="CELERY")
        app.autodiscover_tasks()
        app.autodiscover_tasks(["apps.api.v1"])

        # Celery Beat schedule (Django ONLY)
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

    # ---------------------------
    # FastAPI / standalone workers
    # ---------------------------
    else:
        broker = os.getenv("CELERY_BROKER_URL")
        backend = os.getenv("CELERY_RESULT_BACKEND")

        if not broker:
            raise RuntimeError("CELERY_BROKER_URL must be set")

        app.conf.broker_url = broker
        app.conf.result_backend = backend

    # ---------------------------
    # Global production defaults
    # ---------------------------
    app.conf.update(
        # Time
        timezone="UTC",
        enable_utc=True,

        # Concurrency & performance
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=500,

        # Reliability
        broker_connection_retry_on_startup=True,
        task_reject_on_worker_lost=True,

        # Time limits
        task_soft_time_limit=270,
        task_time_limit=300,

        # Routing
        task_default_queue="default",
        task_routes={
            "apps.*.tasks.*": {"queue": "default"},
            "apps.api.v1.tasks.post_task.cleanup_failed_posts": {"queue": "slow"},
        },
    )

    logger.info("Celery app initialized (django=%s)", django_enabled())
    return app


# ------------------------------------------------------------------------------
# Singleton access (worker-safe)
# ------------------------------------------------------------------------------

_celery_app: Celery | None = None


def get_celery_app() -> Celery:
    global _celery_app
    if _celery_app is None:
        _celery_app = create_celery_app()
    return _celery_app

celery_app = get_celery_app()
