"""分层记忆 dataclass — 召回预算与命中结果"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LayerName = Literal["l0", "l1", "l2", "l3"]


@dataclass
class RetrieveBudget:
    """分层召回的字符与条数预算"""

    max_chars: int = 3000
    max_l1: int = 8
    max_l2: int = 2
    max_l3: int = 3

    @classmethod
    def default(cls) -> "RetrieveBudget":
        from server.config import settings

        return cls(
            max_chars=settings.MEMORY_RETRIEVE_CHAR_BUDGET,
            max_l1=settings.MEMORY_MAX_L1,
            max_l2=settings.MEMORY_MAX_L2,
            max_l3=settings.MEMORY_MAX_L3,
        )


@dataclass
class MemoryHit:
    """单条记忆召回命中"""

    layer: LayerName
    id: str
    text: str
    score: float
    metadata: dict | None = None

    def chars(self) -> int:
        """文本字符数，用于预算裁剪"""
        return len(self.text or "")
