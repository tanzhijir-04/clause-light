"""LightRAG 适配器开关与降级行为测试"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from server.config import settings


@pytest.mark.asyncio
async def test_search_disabled_returns_empty():
    """默认关闭时不尝试检索，直接返回空列表"""
    from server.core.wiki.lightrag_adapter import search

    with patch.object(settings, "LIGHT_RAG_ENABLED", False):
        assert await search("违约金") == []


@pytest.mark.asyncio
async def test_search_enabled_missing_package_returns_empty(caplog):
    """开启但包不可导入时降级为空列表，并打 warning"""
    from server.core.wiki import lightrag_adapter

    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name in ("lightrag", "lightrag_hku") or name.startswith("lightrag"):
            raise ImportError(f"No module named {name}")
        return real_import(name, *args, **kwargs)

    with (
        patch.object(settings, "LIGHT_RAG_ENABLED", True),
        patch("builtins.__import__", side_effect=_fake_import),
        caplog.at_level("WARNING"),
    ):
        result = await lightrag_adapter.search("违约金")

    assert result == []
    assert any("lightrag" in r.message.lower() for r in caplog.records)


def test_light_rag_enabled_default_false():
    """配置开关默认关闭，测试环境不必安装 LightRAG"""
    assert settings.LIGHT_RAG_ENABLED is False
