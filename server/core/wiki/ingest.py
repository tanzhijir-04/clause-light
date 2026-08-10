"""从 shared/laws JSON 冷启动导入 Wiki 页面"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from server.core.wiki.store import slugify_law_article, upsert_page

logger = logging.getLogger(__name__)


async def ingest_laws(db: AsyncSession, path: str) -> int:
    """
    从法规 JSON 文件导入 Wiki 页面。

    每条生成 slug={law}-{article}，status=active，body=content。
    返回写入/更新条数。
    """
    filepath = Path(path)
    if not filepath.is_file():
        raise FileNotFoundError(f"法规文件不存在: {path}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("法规 JSON 须为数组")

    count = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        law_name = (item.get("law_name") or "").strip()
        article = (item.get("article_number") or "").strip()
        content = (item.get("content") or "").strip()
        if not law_name or not article:
            continue

        slug = slugify_law_article(law_name, article)
        title = f"{law_name}{article}" if not article.startswith("第") else f"{law_name} {article}"
        # 测试夹具常用短名+数字：标题含 article 便于检索断言
        if article.isdigit() or article.replace(".", "").isdigit():
            title = f"{law_name}{article}条"

        await upsert_page(
            db,
            {
                "slug": slug,
                "title": title,
                "body": content,
                "status": "active",
                "source": "import",
                "confidence": 1.0,
            },
        )
        count += 1

    logger.info("Wiki 法规导入完成: %s (%d 条)", path, count)
    return count
