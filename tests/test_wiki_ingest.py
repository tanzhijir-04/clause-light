"""Wiki 法规冷启动导入测试"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LAWS_DIR = _REPO_ROOT / "shared" / "laws"


def _write_laws_fixture(payload: list[dict]) -> Path:
    """在 shared/laws 下写入临时夹具，调用方负责删除"""
    path = _LAWS_DIR / f"_test_ingest_{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_ingest_fixture_laws(db_session):
    fixture = _write_laws_fixture(
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
        ]
    )
    try:
        from server.core.wiki.ingest import ingest_laws

        n = await ingest_laws(db_session, str(fixture))
        await db_session.commit()
        assert n == 2

        from server.core.wiki.store import search_pages

        hits = await search_pages(db_session, "违约金")
        assert any("585" in (h.title + h.body) for h in hits)
    finally:
        fixture.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_get_page_with_links(db_session):
    fixture = _write_laws_fixture(
        [
            {"law_name": "民法典", "article_number": "584", "content": "不履行"},
            {"law_name": "民法典", "article_number": "585", "content": "违约金"},
        ]
    )
    try:
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
    finally:
        fixture.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_rejects_path_outside_shared(db_session, tmp_path):
    """shared/ 外路径必须拒绝"""
    from server.core.wiki.ingest import ingest_laws

    outside = tmp_path / "evil.json"
    outside.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="shared"):
        await ingest_laws(db_session, str(outside))


@pytest.mark.asyncio
async def test_ingest_rejects_path_traversal(db_session):
    """含 .. 且 resolve 后落在 shared/ 外必须拒绝"""
    from server.core.wiki.ingest import ingest_laws

    # shared/laws/../../README.md → 仓库根 README，不在白名单
    rel_escape = str(Path("shared") / "laws" / ".." / ".." / "README.md")
    with pytest.raises(ValueError, match="shared"):
        await ingest_laws(db_session, rel_escape)


@pytest.mark.asyncio
async def test_ingest_bad_json_raises_value_error(db_session):
    """JSONDecodeError 应转为 ValueError（API 层 → 400）"""
    from server.core.wiki.ingest import ingest_laws

    fixture = _LAWS_DIR / f"_test_bad_{uuid.uuid4().hex}.json"
    fixture.write_text("{not-json", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="JSON"):
            await ingest_laws(db_session, str(fixture))
    finally:
        fixture.unlink(missing_ok=True)
