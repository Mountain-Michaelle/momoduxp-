### Money saving ####


from decouple import config
# Broker with visibility timeout (VERY IMPORTANT)
CELERY_BROKER_URL = config('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND')

# Queues
CELERY_TASK_QUEUES = {
    "fast": {"routing_key": "fast"},
    "default": {"routing_key": "default"},
    "slow": {"routing_key": "slow"},
}

CELERY_TASK_DEFAULT_QUEUE = "default"

# Global performance
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Reliability
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
