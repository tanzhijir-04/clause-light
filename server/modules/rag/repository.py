"""M1-A 知识文档和 Chunk 的幂等持久化。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.rag.models import KnowledgeChunk, KnowledgeDocument


class KnowledgeRepository:
    """封装 RAG 文档的查询和写入，保持摄取器不依赖 SQL 细节。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_source_hash(
        self, source_key: str, content_sha256: str
    ) -> KnowledgeDocument | None:
        result = await self.session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.source_key == source_key,
                KnowledgeDocument.content_sha256 == content_sha256,
            )
        )
        return result.scalar_one_or_none()

    async def list_documents(self) -> list[KnowledgeDocument]:
        result = await self.session.execute(
            select(KnowledgeDocument).order_by(KnowledgeDocument.created_at, KnowledgeDocument.id)
        )
        return list(result.scalars().all())

    async def deactivate_source_versions(self, source_key: str) -> None:
        result = await self.session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.source_key == source_key,
                KnowledgeDocument.status == "active",
            )
        )
        for document in result.scalars().all():
            document.status = "disabled"

    async def create_document_with_chunks(
        self,
        document: KnowledgeDocument,
        chunks: list[KnowledgeChunk],
    ) -> None:
        self.session.add(document)
        await self.session.flush()
        for chunk in chunks:
            chunk.document_id = document.id
            self.session.add(chunk)
        await self.session.flush()

    async def list_active_chunks(self) -> list[KnowledgeChunk]:
        result = await self.session.execute(
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(KnowledgeDocument.status == "active")
            .order_by(KnowledgeChunk.document_id, KnowledgeChunk.ordinal)
        )
        return list(result.scalars().all())

    async def list_active_entries(
        self,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        """返回活动文档和 Chunk，供检索器构造完整 Citation。"""
        result = await self.session.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(KnowledgeDocument.status == "active")
            .order_by(KnowledgeChunk.document_id, KnowledgeChunk.ordinal)
        )
        return list(result.all())
