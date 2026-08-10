"""文档入口 — 办公文档走 AnyDoc，图片/扫描件走 PaddleOCR"""

from __future__ import annotations

from dataclasses import dataclass, field

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
