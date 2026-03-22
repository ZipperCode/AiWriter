"""Tests for rate limiter module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from redis.asyncio import Redis

from app.security.rate_limiter import RateLimiter


@pytest.fixture
def mock_redis():
    """Create a mock Redis instance with proper async context manager support."""
    redis = AsyncMock(spec=Redis)

    # Create a mock pipeline that supports async context manager
    mock_pipeline = AsyncMock()
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)

    # Set up pipeline methods to return async mocks that won't be awaited during chaining
    def mock_incr(key):
        return mock_pipeline
    def mock_expire(key, ttl):
        return mock_pipeline

    mock_pipeline.incr = mock_incr
    mock_pipeline.expire = mock_expire

    # Set up pipeline() to return the mock pipeline
    redis.pipeline.return_value = mock_pipeline
    redis._mock_pipeline = mock_pipeline

    return redis


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit(mock_redis):
    """Test that rate limiter allows requests within the limit."""
    # Setup: mock pipeline returns count within limit
    mock_pipeline = mock_redis._mock_pipeline
    mock_pipeline.incr.return_value = AsyncMock()
    mock_pipeline.expire.return_value = AsyncMock()
    mock_pipeline.execute.return_value = [15, True]  # count=15, expire=True

    limiter = RateLimiter(mock_redis, max_requests=60, window_seconds=60)
    result = await limiter.check("test_key")

    assert result is True
    assert mock_redis.pipeline.called


@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit(mock_redis):
    """Test that rate limiter blocks requests over the limit."""
    # Setup: mock pipeline returns count over limit
    mock_pipeline = mock_redis._mock_pipeline
    mock_pipeline.incr.return_value = AsyncMock()
    mock_pipeline.expire.return_value = AsyncMock()
    mock_pipeline.execute.return_value = [61, True]  # count=61, expire=True

    limiter = RateLimiter(mock_redis, max_requests=60, window_seconds=60)
    result = await limiter.check("test_key")

    assert result is False


@pytest.mark.asyncio
async def test_rate_limiter_different_keys_independent(mock_redis):
    """Test that different keys maintain independent counters."""
    # Setup: mock pipeline returns different counts for different keys
    mock_pipeline = mock_redis._mock_pipeline

    # First call for key1: count=10
    # Second call for key2: count=5
    mock_pipeline.incr.return_value = AsyncMock()
    mock_pipeline.expire.return_value = AsyncMock()
    mock_pipeline.execute.side_effect = [[10, True], [5, True]]

    limiter = RateLimiter(mock_redis, max_requests=60, window_seconds=60)

    result1 = await limiter.check("key1")
    assert result1 is True

    result2 = await limiter.check("key2")
    assert result2 is True

    # Both calls should have been made with correct key format
    assert mock_redis.pipeline.call_count == 2


@pytest.mark.asyncio
async def test_rate_limiter_get_remaining(mock_redis):
    """Test get_remaining returns correct count."""
    # Mock redis.get to return async result
    async def mock_get(key):
        return b"25"

    mock_redis.get = mock_get

    limiter = RateLimiter(mock_redis, max_requests=60, window_seconds=60)
    remaining = await limiter.get_remaining("test_key")

    assert remaining == 35  # 60 - 25


@pytest.mark.asyncio
async def test_rate_limiter_get_remaining_no_key(mock_redis):
    """Test get_remaining when key doesn't exist."""
    # Mock redis.get to return None
    async def mock_get(key):
        return None

    mock_redis.get = mock_get

    limiter = RateLimiter(mock_redis, max_requests=60, window_seconds=60)
    remaining = await limiter.get_remaining("test_key")

    assert remaining == 60  # Full limit available
