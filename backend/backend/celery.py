"""
Celery configuration for Momodu SaaS app.
Delegates to shared/celery.py for consistent configuration across Django and FastAPI.
"""

from shared.celery import celery_app

__all__ = ["celery_app"]
