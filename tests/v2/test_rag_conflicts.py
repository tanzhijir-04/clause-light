from __future__ import annotations

import hashlib
import uuid

from server.modules.rag.conflicts import resolve_conflicts
from server.modules.rag.schemas import Citation, RetrievalHit


def _hit(
    *,
    source_type: str,
    content: str,
    source_label: str,
    conflict_key: str | None = None,
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid.uuid4(),
        content=content,
        score=1.0,
        citation=Citation(
            chunk_id=uuid.uuid4(),
            source_label=source_label,
            source_key="shared/source.json",
            source_ref="第一条",
            source_start=0,
            source_end=len(content),
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            source_type=source_type,
            conflict_key=conflict_key,
        ),
    )


def test_conflicting_sources_are_kept_and_law_is_first():
    result = resolve_conflicts(
        [
            _hit(
                source_type="rule",
                content="押金上限为两个月",
                source_label="[内部规则] rental.json｜租赁规则第1条",
                conflict_key="deposit-limit",
            ),
            _hit(
                source_type="law",
                content="押金应当合理约定",
                source_label="[法律法规] 测试法｜第一条",
                conflict_key="deposit-limit",
            ),
        ]
    )

    assert result.conflict_detected is True
    assert result.requires_human_review is True
    assert len(result.hits) == 2
    assert result.hits[0].citation.source_type == "law"


def test_identical_content_is_deduplicated():
    first = _hit(
        source_type="law",
        content="相同内容",
        source_label="[法律法规] 法一｜第一条",
    )
    second = _hit(
        source_type="rule",
        content="相同内容",
        source_label="[内部规则] 规则一｜第一条",
    )

    result = resolve_conflicts([first, second])

    assert len(result.hits) == 1
    assert result.conflict_detected is False


def test_without_explicit_conflict_key_does_not_claim_semantic_conflict():
    result = resolve_conflicts(
        [
            _hit(source_type="law", content="规则甲", source_label="[法律法规] 法一"),
            _hit(source_type="rule", content="规则乙", source_label="[内部规则] 规则一"),
        ]
    )

    assert len(result.hits) == 2
    assert result.conflict_detected is False
