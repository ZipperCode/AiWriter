"""Redis-based rate limiter for LLM API calls."""

from redis.asyncio import Redis


class RateLimiter:
    """
    Sliding window rate limiter using Redis.

    Uses atomic Redis operations (INCR + EXPIRE) to track requests
    within a time window. Thread-safe and distributed.
    """

    def __init__(
        self,
        redis: Redis,
        max_requests: int = 60,
        window_seconds: int = 60,
    ):
        """
        Initialize rate limiter.

        Args:
            redis: Redis async client instance
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.redis = redis
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def check(self, key: str) -> bool:
        """
        Check if request is allowed under rate limit.

        Uses Redis pipeline to atomically increment counter and set expiry.
        Key format: `ratelimit:{key}`

        Args:
            key: Identifier to rate limit (e.g., user ID, API endpoint)

        Returns:
            True if request is within limit, False otherwise
        """
        redis_key = f"ratelimit:{key}"

        # Use pipeline for atomic operation
        async with self.redis.pipeline() as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, self.window_seconds)
            results = await pipe.execute()

        # First result is the incremented count
        current_count = results[0]

        return current_count <= self.max_requests

    async def get_remaining(self, key: str) -> int:
        """
        Get remaining requests in current window.

        Args:
            key: Identifier to rate limit (e.g., user ID, API endpoint)

        Returns:
            Number of remaining requests (could be negative if over limit)
        """
        redis_key = f"ratelimit:{key}"
        current_count_bytes = await self.redis.get(redis_key)

        if current_count_bytes is None:
            current_count = 0
        else:
            current_count = int(current_count_bytes)

        return self.max_requests - current_count
