"""Wiki 资产 REST API"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.wiki import ingest as wiki_ingest
from server.core.wiki import store as wiki_store
from server.models.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wiki", tags=["wiki"])


class IngestBody(BaseModel):
    path: str


@router.get("/search")
async def search_wiki(
    q: str = "",
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """关键词搜索 Wiki 页面"""
    pages = await wiki_store.search_pages(db, q, limit=limit)
    return [wiki_store.page_to_dict(p) for p in pages]


@router.get("/pages/{slug}")
async def get_wiki_page(
    slug: str,
    hop: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """按 slug 获取页面及一跳出链摘要"""
    page = await wiki_store.get_page(db, slug, hop=hop)
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在")
    return page


@router.post("/ingest")
async def ingest_wiki(
    data: IngestBody,
    db: AsyncSession = Depends(get_db),
):
    """从本地 JSON 路径冷启动导入法规 Wiki（仅 shared/laws|rules）"""
    try:
        n = await wiki_ingest.ingest_laws(db, data.path)
        await db.commit()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"success": True, "count": n}
