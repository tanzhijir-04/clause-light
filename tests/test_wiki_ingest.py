"""Wiki 法规冷启动导入测试"""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_ingest_fixture_laws(db_session, tmp_path):
    fixture = tmp_path / "laws.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "law_name": "民法典",
                    "article_number": "584",
                    "content": "当事人一方不履行合同义务...",
                },
                {
                    "law_name": "民法典",
                    "article_number": "585",
                    "content": "约定的违约金低于造成的损失...",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    from server.core.wiki.ingest import ingest_laws

    n = await ingest_laws(db_session, str(fixture))
    await db_session.commit()
    assert n == 2

    from server.core.wiki.store import search_pages

    hits = await search_pages(db_session, "违约金")
    assert any("585" in (h.title + h.body) for h in hits)


@pytest.mark.asyncio
async def test_get_page_with_links(db_session, tmp_path):
    fixture = tmp_path / "laws.json"
    fixture.write_text(
        json.dumps(
            [
                {"law_name": "民法典", "article_number": "584", "content": "不履行"},
                {"law_name": "民法典", "article_number": "585", "content": "违约金"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    from server.core.wiki.ingest import ingest_laws
    from server.core.wiki.store import get_page, slugify_law_article
    from server.models.database import WikiLink, WikiPage
    from sqlalchemy import select

    await ingest_laws(db_session, str(fixture))
    await db_session.flush()

    pages = (await db_session.execute(select(WikiPage))).scalars().all()
    assert len(pages) == 2
    a, b = pages[0], pages[1]
    db_session.add(
        WikiLink(id="l1", from_page_id=a.id, to_page_id=b.id, rel="related")
    )
    await db_session.commit()

    data = await get_page(db_session, a.slug, hop=1)
    assert data is not None
    assert data["slug"] == a.slug
    assert len(data["links"]) == 1
    assert data["links"][0]["slug"] == b.slug
    assert slugify_law_article("民法典", "584") == "民法典-584"
