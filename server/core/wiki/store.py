"""Wiki 页面 CRUD、搜索与一跳链接"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.database import WikiLink, WikiPage

logger = logging.getLogger(__name__)


def slugify_law_article(law_name: str, article_number: str) -> str:
    """生成稳定 slug：{law}-{article}，空白压成连字符"""
    law = re.sub(r"\s+", "-", (law_name or "").strip())
    article = re.sub(r"\s+", "-", (article_number or "").strip())
    return f"{law}-{article}"


def page_to_dict(page: WikiPage, *, links: list[dict] | None = None) -> dict:
    """WikiPage → API 字典"""
    data: dict[str, Any] = {
        "id": page.id,
        "slug": page.slug,
        "title": page.title,
        "body": page.body or "",
        "status": page.status or "pending",
        "source": page.source or "manual",
        "confidence": page.confidence if page.confidence is not None else 0.5,
    }
    if links is not None:
        data["links"] = links
    return data


async def upsert_page(db: AsyncSession, data: dict[str, Any]) -> WikiPage:
    """按 slug upsert Wiki 页面"""
    slug = data["slug"]
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if page is None:
        page = WikiPage(
            id=data.get("id") or uuid.uuid4().hex,
            slug=slug,
            title=data.get("title") or slug,
            body=data.get("body") or "",
            status=data.get("status") or "pending",
            source=data.get("source") or "manual",
            confidence=float(data.get("confidence", 0.5) or 0.5),
            owner_user_id=data.get("owner_user_id") or "local",
            visibility=data.get("visibility") or "private",
        )
        db.add(page)
    else:
        if "title" in data:
            page.title = data["title"]
        if "body" in data:
            page.body = data["body"]
        if "status" in data:
            page.status = data["status"]
        if "source" in data:
            page.source = data["source"]
        if "confidence" in data:
            page.confidence = float(data["confidence"] or 0.5)
    await db.flush()
    return page


async def search_pages(
    db: AsyncSession,
    q: str,
    limit: int = 5,
) -> list[WikiPage]:
    """关键词搜索 active Wiki 页面（title/body 子串匹配）"""
    stmt = select(WikiPage).where(WikiPage.status == "active")
    result = await db.execute(stmt)
    pages = list(result.scalars().all())

    query = (q or "").strip().lower()
    if not query:
        return pages[: max(1, limit)]

    hits: list[tuple[int, WikiPage]] = []
    for page in pages:
        blob = f"{page.title or ''} {page.body or ''}".lower()
        if query not in blob:
            continue
        # 标题命中加权
        score = 2 if query in (page.title or "").lower() else 1
        hits.append((score, page))

    hits.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in hits[: max(1, limit)]]


async def get_page(
    db: AsyncSession,
    slug: str,
    hop: int = 1,
) -> dict | None:
    """
    按 slug 取页面；hop>=1 时附带出链页面摘要（最多 5 个）。
    """
    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()
    if page is None:
        return None

    links: list[dict] = []
    if hop >= 1:
        link_rows = (
            await db.execute(
                select(WikiLink).where(WikiLink.from_page_id == page.id)
            )
        ).scalars().all()
        for link in link_rows[:5]:
            target = await db.get(WikiPage, link.to_page_id)
            if target is None:
                continue
            links.append(
                {
                    "rel": link.rel or "related",
                    "slug": target.slug,
                    "title": target.title,
                    "status": target.status,
                }
            )

    return page_to_dict(page, links=links)
