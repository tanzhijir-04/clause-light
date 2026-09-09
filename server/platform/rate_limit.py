"""固定窗口限流，Redis 不可用时使用进程内降级。"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from server.config import settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiter:
    """为租户或 API 凭据提供固定窗口限流。"""

    def __init__(
        self,
        redis_client: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.redis_client = redis_client
        self.clock = clock
        self._local: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        """增加一次计数并返回是否允许请求。"""
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit 和 window_seconds 必须为正数")
        if self.redis_client is not None:
            try:
                return await self._allow_redis(key, limit, window_seconds)
            except Exception as error:
                if settings.REDIS_REQUIRED:
                    raise RuntimeError("Redis 限流依赖不可用") from error
                logger.warning("Redis 限流不可用，切换进程内降级: %s", type(error).__name__)
                self.redis_client = None
        return await self._allow_local(key, limit, window_seconds)

    async def _allow_redis(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitDecision:
        namespaced_key = f"clauselight:rate:{key}"
        count = int(await self.redis_client.incr(namespaced_key))
        if count == 1:
            await self.redis_client.expire(namespaced_key, window_seconds)
        ttl = int(await self.redis_client.ttl(namespaced_key))
        retry_after = max(ttl, 0) if ttl >= 0 else window_seconds
        return RateLimitDecision(
            allowed=count <= limit,
            remaining=max(limit - count, 0),
            retry_after_seconds=0 if count <= limit else retry_after,
        )

    async def _allow_local(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitDecision:
        async with self._lock:
            now = self.clock()
            current_count, expires_at = self._local.get(key, (0, now))
            if now >= expires_at:
                current_count = 0
                expires_at = now + window_seconds
            current_count += 1
            self._local[key] = (current_count, expires_at)
            allowed = current_count <= limit
            return RateLimitDecision(
                allowed=allowed,
                remaining=max(limit - current_count, 0),
                retry_after_seconds=(
                    0 if allowed else max(math.ceil(expires_at - now), 1)
                ),
            )
