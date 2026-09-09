"""M1-A RAG 摄取和检索使用的稳定数据对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid
from typing import Protocol, Sequence


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


@dataclass(frozen=True)
class RetrievalContext:
    """检索所需的租户和可见性上下文。"""

    organization_id: uuid.UUID | None
    contract_type: str | None = None
    allowed_visibility: frozenset[str] = frozenset({"public", "team", "private"})


@dataclass(frozen=True)
class Citation:
    """指向知识源中一个稳定位置的引用。"""

    chunk_id: uuid.UUID
    source_label: str
    source_key: str
    source_ref: str | None
    source_start: int
    source_end: int
    content_sha256: str


@dataclass(frozen=True)
class RetrievalHit:
    """单个检索命中及其来源。"""

    chunk_id: uuid.UUID
    content: str
    score: float
    citation: Citation


@dataclass(frozen=True)
class ContextPackage:
    """受预算限制、可直接交给后续审查链的上下文包。"""

    query: str
    hits: tuple[RetrievalHit, ...]
    total_chars: int
    degraded_mode: str
    degraded_reason: str | None = None
    conflict_detected: bool = False
    requires_human_review: bool = False


class EmbeddingProvider(Protocol):
    """可选本地 Embedding 适配器，不要求具体模型实现。"""

    async def embed(self, text: str) -> Sequence[float] | None:
        """返回单条文本的归一化向量，失败时返回 None。"""
