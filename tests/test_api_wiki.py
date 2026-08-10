"""Wiki REST API 测试"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.models.database import get_db

_REPO_ROOT = Path(__file__).resolve().parents[1]
_LAWS_DIR = _REPO_ROOT / "shared" / "laws"


@pytest_asyncio.fixture
async def wiki_client() -> AsyncGenerator[AsyncClient, None]:
    """仅挂载 wiki 路由"""
    from fastapi import FastAPI

    from server.api.wiki import router
    from tests.conftest import override_get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_search_and_get(wiki_client, db_session):
    fixture = _LAWS_DIR / f"_test_api_{uuid.uuid4().hex}.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "law_name": "民法典",
                    "article_number": "585",
                    "content": "约定的违约金低于造成的损失...",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    try:
        r = await wiki_client.post("/api/wiki/ingest", json={"path": str(fixture)})
        assert r.status_code == 200
        assert r.json()["count"] == 1

        s = await wiki_client.get("/api/wiki/search", params={"q": "违约金"})
        assert s.status_code == 200
        hits = s.json()
        assert len(hits) >= 1
        slug = hits[0]["slug"]

        p = await wiki_client.get(f"/api/wiki/pages/{slug}")
        assert p.status_code == 200
        assert "违约金" in p.json()["body"]
        assert "links" in p.json()
    finally:
        fixture.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_rejects_outside_shared(wiki_client, tmp_path):
    """API：shared/ 外路径 → 400"""
    outside = tmp_path / "evil.json"
    outside.write_text("[]", encoding="utf-8")
    r = await wiki_client.post("/api/wiki/ingest", json={"path": str(outside)})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ingest_bad_json_returns_400(wiki_client):
    """API：非法 JSON → 400"""
    fixture = _LAWS_DIR / f"_test_api_bad_{uuid.uuid4().hex}.json"
    fixture.write_text("{bad", encoding="utf-8")
    try:
        r = await wiki_client.post("/api/wiki/ingest", json={"path": str(fixture)})
        assert r.status_code == 400
    finally:
        fixture.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_get_missing_page(wiki_client):
    r = await wiki_client.get("/api/wiki/pages/not-exist")
    assert r.status_code == 404
