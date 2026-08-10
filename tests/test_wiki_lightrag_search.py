"""Wiki search_pages 可选委托 LightRAG 的合并行为"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from server.config import settings
from server.core.wiki.store import search_pages, upsert_page


async def _seed_pages(db_session):
    rag_only = await upsert_page(
        db_session,
        {
            "slug": "民法典-999",
            "title": "民法典第999条",
            "body": "仅图检索可命中的独特条文",
            "status": "active",
            "source": "law",
        },
    )
    keyword_hit = await upsert_page(
        db_session,
        {
            "slug": "民法典-585",
            "title": "民法典第585条",
            "body": "约定的违约金低于造成的损失",
            "status": "active",
            "source": "law",
        },
    )
    await db_session.commit()
    return rag_only, keyword_hit


@pytest.mark.asyncio
async def test_search_pages_keyword_fallback_when_disabled(db_session):
    """关闭 LightRAG 时仍走关键词检索"""
    await _seed_pages(db_session)

    with patch.object(settings, "LIGHT_RAG_ENABLED", False):
        hits = await search_pages(db_session, "违约金", limit=5)

    assert [p.slug for p in hits] == ["民法典-585"]


@pytest.mark.asyncio
async def test_search_pages_prepends_lightrag_hits(db_session):
    """开启时优先合并 adapter 返回的 slug，关键词结果殿后且去重"""
    await _seed_pages(db_session)

    with (
        patch.object(settings, "LIGHT_RAG_ENABLED", True),
        patch(
            "server.core.wiki.lightrag_adapter.search",
            new_callable=AsyncMock,
            return_value=["民法典-999"],
        ),
    ):
        hits = await search_pages(db_session, "违约金", limit=5)

    slugs = [p.slug for p in hits]
    assert slugs[0] == "民法典-999"
    assert "民法典-585" in slugs


@pytest.mark.asyncio
async def test_search_pages_keyword_when_adapter_empty(db_session):
    """开启但 adapter 空结果时仍保留关键词命中"""
    await _seed_pages(db_session)

    with (
        patch.object(settings, "LIGHT_RAG_ENABLED", True),
        patch(
            "server.core.wiki.lightrag_adapter.search",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        hits = await search_pages(db_session, "违约金", limit=5)

    assert [p.slug for p in hits] == ["民法典-585"]
