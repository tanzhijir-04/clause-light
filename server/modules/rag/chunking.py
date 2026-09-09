"""M1-A 来源文本规范化、分块和来源标签生成。"""

from __future__ import annotations

import re
from typing import Any

from server.modules.rag.schemas import CanonicalText, IngestedChunk, TextChunk


def canonicalize_text(text: str) -> CanonicalText:
    """统一换行、去除行空白和空行，并保留近似坐标映射。"""
    original = text or ""
    normalized_newlines = re.sub(r"\r\n?", "\n", original)
    lines = [line.strip() for line in normalized_newlines.split("\n") if line.strip()]
    canonical = "\n".join(lines)

    mapping: list[int] = []
    cursor = 0
    for char in original:
        if char in "\r\n \t":
            mapping.append(min(cursor, len(canonical)))
            continue
        position = canonical.find(char, cursor)
        if position < 0:
            position = min(cursor, len(canonical))
        mapping.append(position)
        cursor = position + 1
    return CanonicalText(canonical, tuple(mapping))


def _last_boundary(text: str, start: int, end: int) -> int | None:
    """返回窗口内最后一个语义边界。"""
    candidates = [text.rfind(separator, start, end) + 1 for separator in "。！？；\n"]
    valid = [position for position in candidates if position > start]
    return max(valid) if valid else None


def chunk_text(
    text: str,
    *,
    heading: str | None = None,
    max_chars: int = 800,
    overlap_chars: int = 80,
    offset_base: int = 0,
) -> list[TextChunk]:
    """按语义边界分块，返回规范化文本坐标。"""
    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars 必须位于 [0, max_chars) 区间")

    canonical = canonicalize_text(text)
    content = canonical.text
    if not content:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(content):
        hard_end = min(start + max_chars, len(content))
        end = hard_end
        if hard_end < len(content):
            boundary = _last_boundary(content, start, hard_end)
            if boundary is not None and boundary >= start + max_chars // 2:
                end = boundary

        chunks.append(
            TextChunk(
                content=content[start:end],
                source_start=start + offset_base,
                source_end=end + offset_base,
                heading=heading,
            )
        )
        if end >= len(content):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


def chunk_law_record(
    record: dict[str, Any], *, source_key: str, offset_base: int = 0
) -> list[IngestedChunk]:
    """把法规记录转为带法规来源标签的 Chunk。"""
    law_name = str(record.get("law_name", "")).strip()
    article_number = str(record.get("article_number", "")).strip() or None
    content = str(record.get("content", ""))
    source_ref = article_number or "正文"
    source_label = f"[法律法规] {law_name}｜{source_ref}"
    topic_tags = tuple(str(tag) for tag in (record.get("tags") or []))
    metadata = {
        "source_type": "law",
        "source_ref": source_ref,
        "source_title": law_name,
        "source_key": source_key,
        "topic_tags": list(topic_tags),
        "effective_date": record.get("effective_date"),
        "verified_at": record.get("verified_at"),
    }
    chunks = chunk_text(content, heading=article_number, offset_base=offset_base)
    return [
        IngestedChunk(
            content=chunk.content,
            source_start=chunk.source_start,
            source_end=chunk.source_end,
            heading=chunk.heading,
            source_ref=source_ref,
            source_label=source_label,
            source_url=record.get("source_url"),
            topic_tags=topic_tags,
            metadata=metadata,
        )
        for chunk in chunks
    ]


def chunk_rule_record(
    record: dict[str, Any], *, source_key: str, ordinal: int, offset_base: int = 0
) -> list[IngestedChunk]:
    """把内部规则记录转为带文件来源标签的 Chunk。"""
    category = str(record.get("category", "")).strip()
    source_ref = f"{category}规则第{ordinal + 1}条"
    source_label = f"[内部规则] {source_key}｜{source_ref}"
    topic_tags = tuple(
        str(tag)
        for tag in (record.get("trigger_keywords") or [])
    )
    metadata = {
        "source_type": "rule",
        "source_ref": source_ref,
        "source_title": category,
        "source_key": source_key,
        "topic_tags": list(topic_tags),
        "confidence": record.get("confidence"),
        "rule_source": record.get("source"),
    }
    chunks = chunk_text(
        str(record.get("rule_text", "")),
        heading=category,
        offset_base=offset_base,
    )
    return [
        IngestedChunk(
            content=chunk.content,
            source_start=chunk.source_start,
            source_end=chunk.source_end,
            heading=chunk.heading,
            source_ref=source_ref,
            source_label=source_label,
            source_url=None,
            topic_tags=topic_tags,
            metadata=metadata,
        )
        for chunk in chunks
    ]
