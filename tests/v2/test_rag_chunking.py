from __future__ import annotations

from server.modules.rag.chunking import (
    canonicalize_text,
    chunk_law_record,
    chunk_rule_record,
    chunk_text,
)


def test_canonicalize_text_normalizes_line_endings_and_offsets():
    canonical = canonicalize_text("甲\r\n\r\n  乙  ")

    assert canonical.text == "甲\n乙"
    assert len(canonical.original_to_normalized) == len("甲\r\n\r\n  乙  ")


def test_law_record_keeps_article_as_one_chunk():
    chunks = chunk_law_record(
        {
            "law_name": "测试法",
            "article_number": "第一条",
            "content": "当事人订立合同，可以采用书面形式。",
            "source_url": "https://example.invalid/law.pdf",
            "tags": ["合同形式"],
        },
        source_key="shared/laws/sample_law.json",
    )

    assert len(chunks) == 1
    assert chunks[0].source_label == "[法律法规] 测试法｜第一条"
    assert chunks[0].topic_tags == ("合同形式",)
    assert chunks[0].source_ref == "第一条"


def test_rule_record_uses_source_label_and_keeps_topic_tags():
    chunk = chunk_rule_record(
        {
            "category": "租赁",
            "rule_text": "押金应当合理",
            "trigger_keywords": ["押金"],
        },
        source_key="shared/rules/sample_rules.json",
        ordinal=0,
    )[0]

    assert chunk.source_label == "[内部规则] shared/rules/sample_rules.json｜租赁规则第1条"
    assert chunk.topic_tags == ("押金",)


def test_long_content_splits_only_at_sentence_boundaries():
    content = "第一句。" * 250

    chunks = chunk_text(content, heading="第一条", max_chars=800, overlap_chars=80)

    assert len(chunks) > 1
    assert all(chunk.content.strip() for chunk in chunks)
    assert all(chunk.source_start < chunk.source_end for chunk in chunks)
    assert all(
        left.source_start < right.source_start
        for left, right in zip(chunks, chunks[1:])
    )
