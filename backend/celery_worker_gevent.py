from gevent import monkey

monkey.patch_all()

# IMPORTANT: Import models in correct order BEFORE celery app
# This ensures SQLAlchemy relationships resolve correctly
from shared.models.users import User  # noqa
from shared.models.notifications import NotificationConnection, NotificationDelivery  # noqa
from shared.models.posts import ScheduledPost, PostStatus  # noqa

from shared.celery import celery_app  # noqa
