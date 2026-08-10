"""Noop 团队记忆适配器 — 本地单机默认实现"""

from __future__ import annotations

from typing import Any


class NoopTeamMemoryAdapter:
    """不与任何团队服务通信的空实现"""

    async def push_assets(self, assets: list[dict[str, Any]]) -> int:
        """忽略推送，返回 0"""
        return 0

    async def pull_assets(self, since_iso: str | None = None) -> list[dict[str, Any]]:
        """忽略拉取，返回空列表"""
        return []
