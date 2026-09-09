"""Redis 生命周期和不可用降级。"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from server.config import settings


logger = logging.getLogger(__name__)


async def create_redis_client() -> Redis | None:
    """创建并探活 Redis；开发环境不可用时返回 None。"""
    if not settings.REDIS_URL:
        return None
    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.ping()
        return client
    except Exception as error:
        await client.aclose()
        if settings.REDIS_REQUIRED:
            raise RuntimeError("Redis 为生产必需依赖但当前不可用") from error
        logger.warning("Redis 不可用，启用进程内降级: %s", type(error).__name__)
        return None
