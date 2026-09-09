from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.modules.rag.ingest import KnowledgeIngestor, SourceValidationError
from server.modules.rag.models import KnowledgeDocument
from server.modules.rag.repository import KnowledgeRepository


FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "rag"


async def test_ingest_law_file_creates_document_and_chunks(v2_session):
    result = await KnowledgeIngestor(v2_session).ingest_file(
        FIXTURE_ROOT / "sample_law.json",
        source_key="shared/laws/sample_law.json",
    )

    assert result.created is True
    assert result.created_chunks == 1
    assert result.source_type == "law"
    assert result.source_title == "测试法"

    documents = await KnowledgeRepository(v2_session).list_documents()
    assert len(documents) == 1
    assert documents[0].metadata_json["record_count"] == 1


async def test_ingest_same_source_hash_is_idempotent(v2_session):
    ingestor = KnowledgeIngestor(v2_session)
    first = await ingestor.ingest_file(
        FIXTURE_ROOT / "sample_rules.json",
        source_key="shared/rules/sample_rules.json",
    )
    second = await ingestor.ingest_file(
        FIXTURE_ROOT / "sample_rules.json",
        source_key="shared/rules/sample_rules.json",
    )

    assert second.created is False
    assert second.document_id == first.document_id
    assert second.created_chunks == 0
    assert len(await KnowledgeRepository(v2_session).list_documents()) == 1


async def test_changed_source_creates_new_active_version(v2_session, tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(
        json.dumps(
            [{"category": "租赁", "rule_text": "原规则", "trigger_keywords": []}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ingestor = KnowledgeIngestor(v2_session)
    first = await ingestor.ingest_file(path, source_key="shared/rules/rules.json")

    path.write_text(
        json.dumps(
            [{"category": "租赁", "rule_text": "新规则", "trigger_keywords": []}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    second = await ingestor.ingest_file(path, source_key="shared/rules/rules.json")

    assert second.created is True
    assert second.document_id != first.document_id
    documents = await KnowledgeRepository(v2_session).list_documents()
    assert {document.status for document in documents} == {"active", "disabled"}


async def test_invalid_json_does_not_create_partial_document(v2_session, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(SourceValidationError) as error:
        await KnowledgeIngestor(v2_session).ingest_file(
            path,
            source_key="shared/laws/broken.json",
        )

    assert error.value.source_key == "shared/laws/broken.json"
    assert "正文" not in str(error.value)
    assert await KnowledgeRepository(v2_session).list_documents() == []


async def test_invalid_record_rejects_whole_file(v2_session, tmp_path):
    path = tmp_path / "partial.json"
    path.write_text(
        json.dumps(
            [
                {"law_name": "测试法", "article_number": "第一条", "content": "有效"},
                {"law_name": "测试法", "article_number": "第二条"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(SourceValidationError):
        await KnowledgeIngestor(v2_session).ingest_file(
            path,
            source_key="shared/laws/partial.json",
        )

    assert await KnowledgeRepository(v2_session).list_documents() == []
