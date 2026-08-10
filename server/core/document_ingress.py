"""文档入口 — 办公文档走 AnyDoc，图片/扫描件走 PaddleOCR"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

OFFICE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".odt",
    ".ods",
    ".odp",
    ".rtf",
    ".epub",
    ".csv",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
PDF_EXTENSIONS = {".pdf"}


@dataclass
class DocumentResult:
    """统一文档解析结果（内容可为 Markdown）"""

    full_text: str = ""
    markdown: str = ""
    source: str = "anydoc"  # anydoc|paddle|hybrid|pymupdf
    confidence_avg: float = 0.0
    pages: list[dict] = field(default_factory=list)


def _anydoc_to_markdown_sync(path: str) -> str:
    """同步调用本地 AnyDoc（无云端 API）"""
    try:
        import anydoc
    except ImportError as exc:
        raise RuntimeError(
            "firecrawl-anydoc 未安装或当前平台无可用 wheel。"
            "请运行: pip install firecrawl-anydoc"
        ) from exc

    if not hasattr(anydoc, "to_markdown"):
        raise RuntimeError(
            "已安装的 anydoc 模块缺少 to_markdown；请升级 firecrawl-anydoc"
        )

    return anydoc.to_markdown(path)


async def _convert_with_anydoc(path: str) -> str:
    """将文档转为 Markdown；同步库经 asyncio.to_thread 包装"""
    return await asyncio.to_thread(_anydoc_to_markdown_sync, path)


async def ingest(path: str, force_route: str | None = None) -> DocumentResult:
    """
    统一文档入口。

    force_route 仅测试用：anydoc | paddle | pymupdf
    Task 2 先实现 anydoc 调度；完整路由在 Task 3。
    """
    suffix = Path(path).suffix.lower()
    route = force_route

    if route is None:
        if suffix in OFFICE_EXTENSIONS or suffix in PDF_EXTENSIONS:
            route = "anydoc"
        elif suffix in IMAGE_EXTENSIONS:
            route = "paddle"
        else:
            raise ValueError(f"不支持的文件格式: {suffix or '(无扩展名)'}")

    if route == "anydoc":
        markdown = await _convert_with_anydoc(path)
        text = markdown or ""
        return DocumentResult(
            full_text=text,
            markdown=text,
            source="anydoc",
            confidence_avg=1.0,
        )

    raise ValueError(f"未知或尚未实现的路由: {route}")
