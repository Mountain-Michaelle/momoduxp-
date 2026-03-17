# infrastructure/rate_limit.py
# Interface only – implementation swap is trivial

class RateLimiter:
    async def check(self, key: str) -> None:
        raise NotImplementedError
