from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from server.modules.rag.models import KnowledgeChunk, KnowledgeDocument


async def test_knowledge_document_and_chunk_store_provenance(v2_session):
    document = KnowledgeDocument(
        source_type="law",
        source_key="shared/laws/civil_code.json",
        source_title="中华人民共和国民法典",
        content_sha256="a" * 64,
        status="active",
        metadata_json={"effective_date": "2021-01-01"},
    )
    v2_session.add(document)
    await v2_session.flush()

    chunk = KnowledgeChunk(
        document_id=document.id,
        ordinal=0,
        heading="第四百六十九条",
        content="当事人订立合同，可以采用书面形式。",
        source_start=0,
        source_end=20,
        content_sha256="b" * 64,
        visibility="public",
        metadata_json={
            "source_ref": "第四百六十九条",
            "source_label": "[法律法规] 中华人民共和国民法典｜第四百六十九条",
            "topic_tags": ["合同形式"],
        },
    )
    v2_session.add(chunk)
    await v2_session.commit()

    assert chunk.document_id == document.id
    assert chunk.source_start < chunk.source_end
    assert chunk.visibility == "public"
    assert chunk.metadata_json["source_label"].startswith("[法律法规]")


async def test_document_source_hash_is_unique(v2_session):
    values = {
        "source_type": "rule",
        "source_key": "shared/rules/rental.json",
        "source_title": "租赁规则",
        "content_sha256": "c" * 64,
    }
    v2_session.add(KnowledgeDocument(**values))
    await v2_session.commit()

    v2_session.add(KnowledgeDocument(**values))
    with pytest.raises(IntegrityError):
        await v2_session.commit()
    await v2_session.rollback()


async def test_chunk_has_document_identity(v2_session):
    document_id = uuid.uuid4()
    chunk = KnowledgeChunk(
        document_id=document_id,
        ordinal=0,
        content="测试条款",
        source_start=0,
        source_end=4,
        content_sha256="d" * 64,
    )
    assert chunk.document_id == document_id
