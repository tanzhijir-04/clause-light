"""文档入口 — 办公文档走 AnyDoc，图片/扫描件走 PaddleOCR"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from server.core.ocr import OCRResult, PYMUPDF_MIN_TEXT_LEN, get_ocr_engine

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
# 纯文本（WebSocket 手机端先落盘为 .txt 再走分析）
TEXT_EXTENSIONS = {".txt", ".md"}

# 上传白名单：办公文档 + 图片 + PDF（不含纯文本，文本走 WS）
ALLOWED_UPLOAD_EXTENSIONS = OFFICE_EXTENSIONS | IMAGE_EXTENSIONS | PDF_EXTENSIONS


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


def _ocr_to_document(ocr: OCRResult, source: str = "paddle") -> DocumentResult:
    """将 OCRResult 映射为 DocumentResult"""
    text = ocr.full_text or ""
    return DocumentResult(
        full_text=text,
        markdown=text,
        source=source,
        confidence_avg=ocr.confidence_avg,
        pages=list(ocr.pages or []),
    )


def _text_enough(text: str) -> bool:
    return len((text or "").strip()) >= PYMUPDF_MIN_TEXT_LEN


async def _from_paddle(path: str) -> DocumentResult:
    engine = get_ocr_engine()
    ocr = await engine.recognize(path)
    return _ocr_to_document(ocr, source="paddle")


async def _from_anydoc(path: str) -> DocumentResult:
    markdown = await _convert_with_anydoc(path)
    text = markdown or ""
    return DocumentResult(
        full_text=text,
        markdown=text,
        source="anydoc",
        confidence_avg=1.0,
    )


async def _ingest_pdf(path: str) -> DocumentResult:
    """
    PDF 路由：优先 AnyDoc / PyMuPDF 文字层；不足 100 字则 Paddle；
    AnyDoc 与 Paddle 均有贡献时标记 hybrid。
    """
    anydoc_text = ""
    try:
        anydoc_text = (await _convert_with_anydoc(path)) or ""
    except Exception as exc:
        logger.warning("AnyDoc 解析 PDF 失败，将降级 PyMuPDF/Paddle: %s", exc)

    engine = get_ocr_engine()
    pymupdf_result = engine._extract_text_pymupdf(path)
    pymupdf_text = pymupdf_result.full_text or ""

    if _text_enough(anydoc_text):
        return DocumentResult(
            full_text=anydoc_text,
            markdown=anydoc_text,
            source="anydoc",
            confidence_avg=1.0,
        )

    if _text_enough(pymupdf_text):
        return _ocr_to_document(pymupdf_result, source="pymupdf")

    # 文字层不足：走现有 OCREngine（内部会再探 PyMuPDF 后转图 + Paddle）
    paddle_doc = await _from_paddle(path)
    paddle_text = paddle_doc.full_text or ""

    anydoc_has = bool(anydoc_text.strip())
    paddle_has = bool(paddle_text.strip())

    # 两者都有贡献且 Paddle 仍不足时合并为 hybrid；Paddle 足够则优先 paddle
    if anydoc_has and paddle_has and not _text_enough(paddle_text):
        merged = anydoc_text.strip() + "\n\n" + paddle_text.strip()
        return DocumentResult(
            full_text=merged,
            markdown=merged,
            source="hybrid",
            confidence_avg=paddle_doc.confidence_avg,
            pages=paddle_doc.pages,
        )

    if paddle_has:
        return paddle_doc

    if anydoc_has:
        return DocumentResult(
            full_text=anydoc_text,
            markdown=anydoc_text,
            source="anydoc",
            confidence_avg=1.0,
        )

    if pymupdf_text.strip():
        return _ocr_to_document(pymupdf_result, source="pymupdf")

    return paddle_doc


def _detect_image_magic(header: bytes) -> bool:
    """常见图片魔数（不依赖扩展名）"""
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header.startswith((b"GIF87a", b"GIF89a")):
        return True
    if header.startswith(b"BM"):
        return True
    # TIFF little/big endian
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return True
    # WEBP: RIFF....WEBP
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return True
    return False


def _detect_route(path: str) -> str:
    """
    按内容魔数优先、扩展名兜底，返回路由键：
    text | image | office | pdf
    """
    suffix = Path(path).suffix.lower()
    header = b""
    try:
        with open(path, "rb") as f:
            header = f.read(64)
    except OSError as exc:
        logger.warning("读取文件头失败，回退扩展名路由: %s", exc)

    if header.startswith(b"%PDF"):
        return "pdf"
    if _detect_image_magic(header):
        return "image"

    # AnyDoc 内容检测（办公格式）
    try:
        import anydoc

        fmt = None
        if hasattr(anydoc, "format_from_bytes") and header:
            # 部分格式需要更多字节
            with open(path, "rb") as f:
                data = f.read(65536)
            fmt = anydoc.format_from_bytes(data)
        if not fmt and hasattr(anydoc, "format_from_path"):
            fmt = anydoc.format_from_path(path)
        if fmt == "pdf":
            return "pdf"
        if fmt in {
            "doc", "docx", "ppt", "pptx", "xls", "xlsx",
            "odt", "ods", "odp", "rtf", "epub", "csv",
        }:
            return "office"
    except Exception as exc:
        logger.debug("anydoc 格式探测跳过: %s", exc)

    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in OFFICE_EXTENSIONS:
        return "office"
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    raise ValueError(f"不支持的文件格式: {suffix or '(无扩展名)'}")


async def ingest(path: str, force_route: str | None = None) -> DocumentResult:
    """
    统一文档入口。

    路由（魔数优先，扩展名兜底）：
    - TEXT (.txt/.md) → 直接读文件 → source=text
    - IMAGE → OCREngine.recognize → source=paddle
    - OFFICE → AnyDoc → source=anydoc
    - PDF → AnyDoc / PyMuPDF 探文字；不足则 Paddle；可 hybrid
    force_route 仅测试用：anydoc | paddle | pymupdf
    """
    if force_route == "anydoc":
        return await _from_anydoc(path)
    if force_route == "paddle":
        return await _from_paddle(path)
    if force_route == "pymupdf":
        engine = get_ocr_engine()
        return _ocr_to_document(engine._extract_text_pymupdf(path), source="pymupdf")
    if force_route is not None:
        raise ValueError(f"未知 force_route: {force_route}")

    route = _detect_route(path)
    if route == "text":
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return DocumentResult(
            full_text=text,
            markdown=text,
            source="text",
            confidence_avg=1.0,
        )
    if route == "image":
        return await _from_paddle(path)
    if route == "office":
        return await _from_anydoc(path)
    if route == "pdf":
        return await _ingest_pdf(path)

    raise ValueError(f"不支持的文件路由: {route}")
