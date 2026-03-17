"""
Celery configuration for Momodu SaaS app.
Delegates to shared/celery.py for consistent configuration across Django and FastAPI.

This module uses lazy loading to avoid "populate() isn't reentrant" errors.
"""

# Lazy import to avoid django.setup() at module level
def _get_celery_app():
    """Get Celery app instance from shared.celery."""
    from shared.celery import get_celery_app
    return get_celery_app()


class _LazyCeleryProxy:
    """Lazy proxy for celery_app."""

    def __getattr__(self, name):
        return getattr(_get_celery_app(), name)

    def __call__(self, *args, **kwargs):
        return _get_celery_app()(*args, **kwargs)


# Export celery_app as a lazy proxy
celery_app = _LazyCeleryProxy()
__all__ = ['celery_app']
