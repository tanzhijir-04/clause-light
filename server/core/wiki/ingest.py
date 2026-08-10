"""从 shared/laws JSON 冷启动导入 Wiki 页面"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from server.core.wiki.store import slugify_law_article, upsert_page

logger = logging.getLogger(__name__)

# server/core/wiki/ingest.py → 仓库根目录
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALLOWED_INGEST_ROOTS = (
    (_REPO_ROOT / "shared" / "laws").resolve(),
    (_REPO_ROOT / "shared" / "rules").resolve(),
)


def _is_under(path: Path, root: Path) -> bool:
    """判断 path 是否位于 root 之下（含 root 本身）"""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_ingest_path(path: str) -> Path:
    """
    解析并校验 ingest 路径：仅允许 shared/laws 或 shared/rules 下的真实路径。
    通过 realpath 消除 ``..`` 后校验，落在白名单外则拒绝。
    """
    resolved = Path(path).resolve()
    if not any(_is_under(resolved, root) for root in _ALLOWED_INGEST_ROOTS):
        raise ValueError(
            f"ingest 路径必须位于 shared/laws 或 shared/rules 下: {path}"
        )
    if not resolved.is_file():
        raise FileNotFoundError(f"法规文件不存在: {path}")
    return resolved


async def ingest_laws(db: AsyncSession, path: str) -> int:
    """
    从法规 JSON 文件导入 Wiki 页面。

    每条生成 slug={law}-{article}，status=active，body=content。
    返回写入/更新条数。
    """
    filepath = resolve_ingest_path(path)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"法规 JSON 解析失败: {e}") from e

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
