from django.core.cache import cache


class IdempotentTaskMixin:
    """
    Prevents duplicate task execution using Redis/Django cache.
    """

    lock_timeout = 300  # seconds

    def acquire_lock(self, key: str) -> bool:
        return cache.add(key, "1", timeout=self.lock_timeout)

    def release_lock(self, key: str):
        cache.delete(key)
