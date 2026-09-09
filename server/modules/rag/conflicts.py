"""M1-A 来源优先级和显式冲突复核。"""

from __future__ import annotations

from dataclasses import dataclass

from server.modules.rag.schemas import RetrievalHit

AUTHORITY_RANK = {
    "rule": 0,
    "organization_policy": 1,
    "official_guidance": 2,
    "law": 3,
}


@dataclass(frozen=True)
class ConflictResolution:
    """冲突处理后的命中列表和复核状态。"""

    hits: tuple[RetrievalHit, ...]
    conflict_detected: bool
    requires_human_review: bool


def _priority(hit: RetrievalHit) -> tuple[int, str, str]:
    citation = hit.citation
    return (
        AUTHORITY_RANK.get(citation.source_type, -1),
        citation.effective_date or "",
        citation.verified_at or "",
    )


def resolve_conflicts(hits: list[RetrievalHit]) -> ConflictResolution:
    """去重并处理显式 conflict_key，不对无 key 内容做语义猜测。"""
    unique: list[RetrievalHit] = []
    seen_hashes: set[str] = set()
    for hit in hits:
        if hit.citation.content_sha256 in seen_hashes:
            continue
        seen_hashes.add(hit.citation.content_sha256)
        unique.append(hit)

    groups: dict[str, list[RetrievalHit]] = {}
    for hit in unique:
        key = hit.citation.conflict_key
        if key:
            groups.setdefault(key, []).append(hit)

    conflict_detected = any(
        len({item.citation.content_sha256 for item in group}) > 1
        for group in groups.values()
        if len(group) > 1
    )
    if not conflict_detected:
        return ConflictResolution(tuple(unique), False, False)

    ordered: list[RetrievalHit] = []
    emitted: set[str] = set()
    for hit in unique:
        key = hit.citation.conflict_key
        if not key or key in emitted:
            continue
        group = groups[key]
        ordered.extend(sorted(group, key=_priority, reverse=True))
        emitted.add(key)

    for hit in unique:
        if hit.citation.conflict_key is None:
            ordered.append(hit)

    return ConflictResolution(tuple(ordered), True, True)
