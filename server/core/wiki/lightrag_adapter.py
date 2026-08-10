"""LightRAG 可选适配器 — 默认关闭，失败降级为空结果"""

from __future__ import annotations

import logging
from typing import Any

from server.config import settings

logger = logging.getLogger(__name__)


def _try_import_lightrag() -> Any | None:
    """尝试导入 lightrag / lightrag_hku；失败返回 None 并打 warning"""
    for name in ("lightrag", "lightrag_hku"):
        try:
            return __import__(name)
        except ImportError:
            continue
    logger.warning(
        "LIGHT_RAG_ENABLED=True 但未安装 lightrag/lightrag-hku，Wiki 图检索降级为空"
    )
    return None


async def search(query: str) -> list[str]:
    """
    可选 LightRAG 检索，返回 wiki slug 列表。

    未开启、包缺失或一期桩模式下均返回 []，由调用方回退关键词检索。
    """
    if not settings.LIGHT_RAG_ENABLED:
        return []

    rag = _try_import_lightrag()
    if rag is None:
        return []

    # 一期降级桩：包可导入也不强制建图索引，交由关键词路径兜底
    _ = query
    return []
