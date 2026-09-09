"""M1-A RAG 摄取和检索使用的稳定数据对象。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanonicalText:
    """规范化文本及原始字符到规范化坐标的近似映射。"""

    text: str
    original_to_normalized: tuple[int, ...]


@dataclass(frozen=True)
class TextChunk:
    """带规范化全文坐标的文本片段。"""

    content: str
    source_start: int
    source_end: int
    heading: str | None = None


@dataclass(frozen=True)
class IngestedChunk:
    """摄取器产生的、尚未写入数据库的知识片段。"""

    content: str
    source_start: int
    source_end: int
    heading: str | None
    source_ref: str | None
    source_label: str
    source_url: str | None
    topic_tags: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
