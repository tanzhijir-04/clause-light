"""团队记忆适配器协议"""

from __future__ import annotations

from typing import Any, Protocol


class TeamMemoryAdapter(Protocol):
    """团队层记忆同步接口（本地可接 Noop，后期可接 TencentDB 等）"""

    async def push_assets(self, assets: list[dict[str, Any]]) -> int:
        """推送资产到团队层，返回成功条数"""
        ...

    async def pull_assets(self, since_iso: str | None = None) -> list[dict[str, Any]]:
        """自 since_iso 起拉取团队资产；None 表示全量"""
        ...
