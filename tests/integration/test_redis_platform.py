from __future__ import annotations

import os
import uuid

import pytest
from redis.asyncio import Redis

from server.platform.progress import ProgressPublisher
from server.platform.rate_limit import RateLimiter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_rate_limit_and_progress_publish() -> None:
    redis_url = os.getenv("INTEGRATION_REDIS_URL")
    if not redis_url:
        pytest.skip("未配置 INTEGRATION_REDIS_URL")

    client = Redis.from_url(redis_url, decode_responses=True)
    key = f"integration-{uuid.uuid4().hex}"
    try:
        assert await client.ping()
        limiter = RateLimiter(client)
        assert (await limiter.allow(key, limit=1, window_seconds=30)).allowed
        assert not (await limiter.allow(key, limit=1, window_seconds=30)).allowed

        publisher = ProgressPublisher(client)
        await publisher.publish(key, {"status": "running", "percent": 40})
        assert publisher.local_snapshot(key) == {"status": "running", "percent": 40}
        assert await client.ttl(f"clauselight:rate:{key}") > 0
    finally:
        await client.delete(f"clauselight:rate:{key}")
        await client.aclose()
