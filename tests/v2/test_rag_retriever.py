from __future__ import annotations

import hashlib
import uuid

from server.modules.rag.models import KnowledgeChunk, KnowledgeDocument
from server.modules.rag.retriever import SQLiteRetriever
from server.modules.rag.schemas import RetrievalContext


async def _add_chunk(
    session,
    *,
    content: str,
    source_label: str,
    visibility: str = "public",
    organization_id: uuid.UUID | None = None,
    acl_json: list[str] | None = None,
    heading: str = "第一条",
):
    document = KnowledgeDocument(
        organization_id=organization_id,
        source_type="law",
        source_key=f"shared/laws/{uuid.uuid4().hex}.json",
        source_title="测试法",
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        source_url="https://example.invalid/law.pdf",
        metadata_json={},
    )
    session.add(document)
    await session.flush()
    chunk = KnowledgeChunk(
        document_id=document.id,
        organization_id=organization_id,
        ordinal=0,
        heading=heading,
        content=content,
        source_start=0,
        source_end=len(content),
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        visibility=visibility,
        acl_json=acl_json,
        metadata_json={
            "source_ref": heading,
            "source_label": source_label,
            "topic_tags": ["违约责任"],
        },
    )
    session.add(chunk)
    await session.flush()
    return chunk


async def test_retriever_returns_source_citation_and_lexical_mode(v2_session):
    await _add_chunk(
        v2_session,
        content="当事人不履行合同义务的，应当承担违约责任。",
        source_label="[法律法规] 测试法｜第一条",
    )

    package = await SQLiteRetriever(v2_session).retrieve(
        "违约责任",
        RetrievalContext(organization_id=uuid.uuid4()),
        top_k=5,
        token_budget=120,
    )

    assert package.degraded_mode == "lexical"
    assert package.hits
    assert package.hits[0].citation.source_label == "[法律法规] 测试法｜第一条"
    assert package.hits[0].citation.source_key.startswith("shared/laws/")
    assert package.hits[0].citation.content_sha256


async def test_retriever_filters_acl_before_scoring(v2_session):
    org_a = uuid.uuid4()
    private_chunk = await _add_chunk(
        v2_session,
        content="组织 A 的私有违约责任规则",
        source_label="[内部规则] org-a｜违约规则",
        visibility="private",
        organization_id=org_a,
        acl_json=[str(org_a)],
    )
    await _add_chunk(
        v2_session,
        content="公共规则不涉及该查询",
        source_label="[法律法规] 公共来源｜第一条",
    )

    package = await SQLiteRetriever(v2_session).retrieve(
        "组织 A 的私有违约责任规则",
        RetrievalContext(organization_id=uuid.uuid4()),
        top_k=5,
    )

    assert all(hit.chunk_id != private_chunk.id for hit in package.hits)


async def test_retriever_does_not_exceed_character_budget(v2_session):
    await _add_chunk(
        v2_session,
        content="违约责任" * 20,
        source_label="[法律法规] 测试法｜第一条",
    )

    package = await SQLiteRetriever(v2_session).retrieve(
        "违约责任",
        RetrievalContext(organization_id=uuid.uuid4()),
        top_k=5,
        token_budget=20,
    )

    assert package.total_chars <= 20
    assert all(len(hit.content) <= 20 for hit in package.hits)


async def test_retriever_returns_empty_for_non_matching_query(v2_session):
    await _add_chunk(
        v2_session,
        content="履行期限和交付地点",
        source_label="[法律法规] 测试法｜第二条",
    )

    package = await SQLiteRetriever(v2_session).retrieve(
        "完全不相关的问题",
        RetrievalContext(organization_id=uuid.uuid4()),
    )

    assert package.hits == ()


async def test_retrieval_trace_reports_filtering_and_budget(v2_session):
    private_chunk = await _add_chunk(
        v2_session,
        content="组织 A 的私有违约责任规则",
        source_label="[内部规则] org-a｜违约规则",
        visibility="private",
        organization_id=uuid.uuid4(),
    )
    await _add_chunk(
        v2_session,
        content="公共来源的违约责任规则",
        source_label="[法律法规] 公共来源｜第一条",
    )
    await _add_chunk(
        v2_session,
        content="公共来源的违约责任规则",
        source_label="[法律法规] 公共来源｜第二条",
    )

    package = await SQLiteRetriever(v2_session).retrieve(
        "违约责任",
        RetrievalContext(organization_id=uuid.uuid4()),
        top_k=5,
        token_budget=80,
    )

    assert package.trace.candidate_count >= package.trace.visible_count
    assert package.trace.acl_filtered_count >= 1
    assert all(hit.chunk_id != private_chunk.id for hit in package.hits)
    assert package.trace.duplicate_count >= 1
    assert package.trace.returned_count == len(package.hits)
    assert package.trace.budget_skipped_count >= 0
    assert package.trace.query_chars == len(package.query)


async def test_invalid_content_hash_is_dropped_and_requires_review(v2_session):
    chunk = await _add_chunk(
        v2_session,
        content="违约责任",
        source_label="[法律法规] 测试法｜第一条",
    )
    chunk.content_sha256 = "0" * 64
    await v2_session.flush()

    package = await SQLiteRetriever(v2_session).retrieve(
        "违约责任",
        RetrievalContext(organization_id=None),
    )

    assert package.hits == ()
    assert package.requires_human_review is True
    assert package.trace.invalid_citation_count == 1
