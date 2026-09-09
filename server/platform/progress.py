"""任务进度发布与 Redis 不可用时的本地快照。"""

from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger(__name__)


class ProgressPublisher:
    """先保存进程内快照，再尽力发布 Redis Pub/Sub 消息。"""

    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis_client = redis_client
        self._snapshots: dict[str, dict] = {}

    async def publish(self, job_id: str, payload: dict) -> None:
        self._snapshots[job_id] = dict(payload)
        if self.redis_client is None:
            return
        try:
            await self.redis_client.publish(
                f"clauselight:jobs:{job_id}",
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception as error:
            logger.warning("任务进度发布失败: job_id=%s error_type=%s", job_id, type(error).__name__)

    def local_snapshot(self, job_id: str) -> dict | None:
        snapshot = self._snapshots.get(job_id)
        return dict(snapshot) if snapshot is not None else None
