"""M1-A SQLite 关键词检索和可选本地 Embedding 评分。"""

from __future__ import annotations

import hashlib
import math
import uuid
from collections.abc import Sequence

from server.modules.rag.conflicts import resolve_conflicts
from server.modules.rag.repository import KnowledgeRepository
from server.modules.rag.schemas import (
    Citation,
    ContextPackage,
    EmbeddingProvider,
    RetrievalContext,
    RetrievalHit,
    RetrievalTrace,
)


def _normalize(value: str) -> str:
    return "".join((value or "").lower().split())


def _as_tags(metadata: dict | None) -> list[str]:
    tags = (metadata or {}).get("topic_tags", [])
    if not isinstance(tags, list):
        return []
    return [str(tag) for tag in tags]


def _is_visible(
    chunk,
    document,
    context: RetrievalContext,
) -> bool:
    if chunk.visibility not in context.allowed_visibility:
        return False
    for owner_id in (document.organization_id, chunk.organization_id):
        if owner_id is not None and owner_id != context.organization_id:
            return False
    if chunk.acl_json:
        allowed = {str(item) for item in chunk.acl_json}
        if context.organization_id is None or str(context.organization_id) not in allowed:
            return False
    return True


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def _citation(chunk, document) -> Citation | None:
    metadata = chunk.metadata_json or {}
    source_label = metadata.get("source_label")
    if not isinstance(source_label, str) or not source_label.strip():
        return None
    if chunk.source_start < 0 or chunk.source_end <= chunk.source_start:
        return None
    if len(chunk.content_sha256) != 64:
        return None
    expected_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
    if chunk.content_sha256 != expected_hash:
        return None
    try:
        uuid.UUID(str(chunk.id))
    except (ValueError, TypeError, AttributeError):
        return None
    return Citation(
        chunk_id=chunk.id,
        source_label=source_label,
        source_key=document.source_key,
        source_ref=metadata.get("source_ref"),
        source_start=chunk.source_start,
        source_end=chunk.source_end,
        content_sha256=chunk.content_sha256,
        source_type=str(metadata.get("source_type", "")),
        conflict_key=(
            str(metadata["conflict_key"])
            if metadata.get("conflict_key") is not None
            else None
        ),
        effective_date=(
            str(metadata["effective_date"])
            if metadata.get("effective_date") is not None
            else None
        ),
        verified_at=(
            str(metadata["verified_at"])
            if metadata.get("verified_at") is not None
            else None
        ),
    )


class SQLiteRetriever:
    """基于 M1-A 知识表的本地检索器。"""

    def __init__(self, session, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.repository = KnowledgeRepository(session)
        self.embedding_provider = embedding_provider

    async def retrieve(
        self,
        query: str,
        context: RetrievalContext,
        top_k: int = 10,
        token_budget: int = 3000,
    ) -> ContextPackage:
        normalized_query = _normalize(query)
        if top_k <= 0 or token_budget <= 0 or not normalized_query:
            return ContextPackage(
                query=normalized_query,
                hits=(),
                total_chars=0,
                degraded_mode="lexical",
            )

        entries = await self.repository.list_active_entries()
        candidate_count = len(entries)
        acl_filtered_count = 0
        visible_count = 0
        scored_count = 0
        invalid_citation_count = 0
        candidates: list[tuple[float, object, object, Citation]] = []
        for chunk, document in entries:
            # ACL 必须在分数计算前完成，不能把不可见数据带入排序。
            if not _is_visible(chunk, document, context):
                acl_filtered_count += 1
                continue
            visible_count += 1
            citation = _citation(chunk, document)
            if citation is None:
                invalid_citation_count += 1
                continue
            content = _normalize(chunk.content)
            heading = _normalize(chunk.heading or "")
            tags = [_normalize(tag) for tag in _as_tags(chunk.metadata_json)]
            score = 0.0
            if normalized_query in content:
                score += 6.0
            if normalized_query in heading or any(normalized_query in tag for tag in tags):
                score += 3.0
            confidence = (chunk.metadata_json or {}).get("confidence")
            if isinstance(confidence, (int, float)):
                score += max(0.0, min(float(confidence), 1.0)) * 0.1
            if score > 0:
                scored_count += 1
                candidates.append((score, chunk, document, citation))

        mode = "lexical"
        degraded_reason: str | None = None
        if self.embedding_provider is not None and candidates:
            try:
                query_vector = await self.embedding_provider.embed(query)
                if query_vector is None:
                    degraded_reason = "embedding_unavailable"
                else:
                    vector_hits = 0
                    for index, (_, chunk, _, _) in enumerate(candidates):
                        vector = chunk.embedding_json
                        if isinstance(vector, list) and vector:
                            score, document_chunk, document, citation = candidates[index]
                            candidates[index] = (
                                score + max(0.0, _cosine(query_vector, vector)) * 3.0,
                                document_chunk,
                                document,
                                citation,
                            )
                            vector_hits += 1
                    if vector_hits:
                        mode = "local_embedding"
                    else:
                        degraded_reason = "chunk_embedding_unavailable"
            except Exception:
                degraded_reason = "embedding_error"

        candidates.sort(
            key=lambda item: (-item[0], item[3].source_label, item[1].ordinal, str(item[1].id))
        )
        hits: list[RetrievalHit] = []
        seen_hashes: set[str] = set()
        total_chars = 0
        duplicate_count = 0
        budget_skipped_count = 0
        for score, chunk, _, citation in candidates:
            if chunk.content_sha256 in seen_hashes:
                duplicate_count += 1
                continue
            if len(hits) >= top_k:
                continue
            if total_chars + len(chunk.content) > token_budget:
                budget_skipped_count += 1
                continue
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.id,
                    content=chunk.content,
                    score=round(score, 6),
                    citation=citation,
                )
            )
            seen_hashes.add(chunk.content_sha256)
            total_chars += len(chunk.content)

        resolution = resolve_conflicts(hits)
        trace = RetrievalTrace(
            query_chars=len(normalized_query),
            candidate_count=candidate_count,
            acl_filtered_count=acl_filtered_count,
            visible_count=visible_count,
            scored_count=scored_count,
            duplicate_count=duplicate_count,
            budget_skipped_count=budget_skipped_count,
            invalid_citation_count=invalid_citation_count,
            returned_count=len(resolution.hits),
        )
        return ContextPackage(
            query=normalized_query,
            hits=resolution.hits,
            total_chars=total_chars,
            degraded_mode=mode,
            degraded_reason=degraded_reason,
            conflict_detected=resolution.conflict_detected,
            requires_human_review=resolution.requires_human_review or invalid_citation_count > 0,
            trace=trace,
        )
