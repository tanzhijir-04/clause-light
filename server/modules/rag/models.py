"""M1-A 知识文档和可检索 Chunk 模型。"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models.base import Base, TimestampMixin


class KnowledgeDocument(TimestampMixin, Base):
    """法规或规则源文件的一个不可变内容版本。"""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint(
            "source_key",
            "content_sha256",
            name="uq_knowledge_documents_source_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_key: Mapped[str] = mapped_column(String(500))
    source_title: Mapped[str] = mapped_column(String(300))
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeChunk(TimestampMixin, Base):
    """保留来源位置和授权元数据的可检索知识片段。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "ordinal",
            name="uq_knowledge_chunks_document_ordinal",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id"), index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    ordinal: Mapped[int]
    heading: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    source_start: Mapped[int]
    source_end: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    embedding_json: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    visibility: Mapped[str] = mapped_column(String(24), default="public", index=True)
    acl_json: Mapped[list[str] | None] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
