"""
Django backend package initialization.
Loads Celery app on Django startup using lazy initialization.

This approach avoids the "populate() isn't reentrant" error by using
lazy loading instead of importing celery at module level.
"""

# For backwards compatibility, expose celery_app via lazy import
# Django will call this when running management commands


def _get_celery_app():
    """Lazy import to avoid django.setup() conflicts."""
    from shared.celery import get_celery_app
    return get_celery_app()


# Create a lazy proxy for celery_app
class _LazyCeleryProxy:
    """Lazy proxy for celery_app to avoid import-time Django setup."""

    def __getattr__(self, name):
        return getattr(_get_celery_app(), name)

    def __call__(self, *args, **kwargs):
        return _get_celery_app()(*args, **kwargs)


celery_app = _LazyCeleryProxy()
__all__ = ('celery_app',)
