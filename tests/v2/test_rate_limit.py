from __future__ import annotations

import pytest

from server.platform.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_in_process_rate_limiter_enforces_window() -> None:
    now = [100.0]
    limiter = RateLimiter(redis_client=None, clock=lambda: now[0])

    first = await limiter.allow("org-1", limit=2, window_seconds=10)
    second = await limiter.allow("org-1", limit=2, window_seconds=10)
    blocked = await limiter.allow("org-1", limit=2, window_seconds=10)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 10

    now[0] = 111.0
    reset = await limiter.allow("org-1", limit=2, window_seconds=10)
    assert reset.allowed is True
    assert reset.remaining == 1
