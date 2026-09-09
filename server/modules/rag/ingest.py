"""M1-A 法规和内部规则 JSON 的本地、幂等摄取。"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.rag.chunking import (
    canonicalize_text,
    chunk_law_record,
    chunk_rule_record,
)
from server.modules.rag.models import KnowledgeChunk, KnowledgeDocument
from server.modules.rag.repository import KnowledgeRepository
from server.modules.rag.schemas import IngestedChunk


class SourceValidationError(ValueError):
    """源文件结构不满足摄取契约。"""

    def __init__(self, source_key: str, field: str, reason: str) -> None:
        self.source_key = source_key
        self.field = field
        self.reason = reason
        super().__init__(f"source={source_key} field={field} reason={reason}")


@dataclass(frozen=True)
class IngestResult:
    """一次文件摄取的摘要，不包含源正文。"""

    document_id: uuid.UUID
    source_key: str
    source_type: str
    source_title: str
    created: bool
    created_chunks: int


@dataclass(frozen=True)
class PreparedSource:
    """已校验且已分块的源文件，不包含数据库状态。"""

    source_key: str
    source_type: str
    source_title: str
    source_hash: str
    source_url: str | None
    record_count: int
    chunks: tuple[IngestedChunk, ...]


def _content_hash(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _required_text(record: dict[str, Any], field: str, source_key: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SourceValidationError(source_key, field, "required_non_empty_string")
    return value.strip()


def _validate_payload(payload: Any, source_key: str) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(payload, list) or not payload:
        raise SourceValidationError(source_key, "root", "expected_non_empty_array")
    if not all(isinstance(record, dict) for record in payload):
        raise SourceValidationError(source_key, "record", "expected_object")

    records = [record for record in payload if isinstance(record, dict)]
    is_law = "law_name" in records[0] or "article_number" in records[0]
    source_type = "law" if is_law else "rule"
    for record in records:
        if source_type == "law":
            _required_text(record, "law_name", source_key)
            _required_text(record, "content", source_key)
        else:
            _required_text(record, "category", source_key)
            _required_text(record, "rule_text", source_key)
    return source_type, records


class KnowledgeIngestor:
    """把本地法规/规则源文件写入 M1-A 知识表。"""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = KnowledgeRepository(session)

    async def ingest_file(
        self,
        file_path: str | Path,
        *,
        source_key: str | None = None,
    ) -> IngestResult:
        prepared = prepare_source_file(file_path, source_key=source_key)
        key = prepared.source_key
        source_type = prepared.source_type
        source_hash = prepared.source_hash
        existing = await self.repository.find_by_source_hash(key, source_hash)
        if existing is not None:
            return IngestResult(
                document_id=existing.id,
                source_key=key,
                source_type=source_type,
                source_title=existing.source_title,
                created=False,
                created_chunks=0,
            )

        chunks_to_store: list[KnowledgeChunk] = []
        for item in prepared.chunks:
            chunks_to_store.append(
                KnowledgeChunk(
                    organization_id=None,
                    ordinal=len(chunks_to_store),
                    heading=item.heading,
                    content=item.content,
                    source_start=item.source_start,
                    source_end=item.source_end,
                    content_sha256=hashlib.sha256(
                        item.content.encode("utf-8")
                    ).hexdigest(),
                    embedding_json=None,
                    embedding_model=None,
                    visibility="public",
                    acl_json=None,
                    metadata_json={
                        **item.metadata,
                        "source_ref": item.source_ref,
                        "source_label": item.source_label,
                        "source_url": item.source_url,
                    },
                )
            )

        document = KnowledgeDocument(
            organization_id=None,
            source_type=source_type,
            source_key=key,
            source_title=prepared.source_title,
            content_sha256=source_hash,
            source_url=prepared.source_url,
            status="active",
            metadata_json={
                "source_type": source_type,
                "source_key": key,
                "record_count": prepared.record_count,
            },
        )
        await self.repository.deactivate_source_versions(key)
        await self.repository.create_document_with_chunks(document, chunks_to_store)
        return IngestResult(
            document_id=document.id,
            source_key=key,
            source_type=source_type,
            source_title=prepared.source_title,
            created=True,
            created_chunks=len(chunks_to_store),
        )


def prepare_source_file(
    file_path: str | Path,
    *,
    source_key: str | None = None,
) -> PreparedSource:
    """读取、校验并分块一个源文件，供 dry-run 与正式摄取复用。"""
    path = Path(file_path)
    key = source_key or path.as_posix()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise SourceValidationError(key, "file", "unreadable") from exc
    except json.JSONDecodeError as exc:
        raise SourceValidationError(key, "json", "invalid_json") from exc

    source_type, records = _validate_payload(payload, key)
    source_hash = _content_hash(payload)
    chunks: list[IngestedChunk] = []
    source_title = ""
    source_url: str | None = None
    offset_base = 0
    for ordinal, record in enumerate(records):
        if source_type == "law":
            source_title = source_title or str(record["law_name"]).strip()
            source_url = source_url or record.get("source_url")
            ingested = chunk_law_record(
                record,
                source_key=key,
                offset_base=offset_base,
            )
            record_text = str(record["content"])
        else:
            source_title = source_title or path.stem
            ingested = chunk_rule_record(
                record,
                source_key=key,
                ordinal=ordinal,
                offset_base=offset_base,
            )
            record_text = str(record["rule_text"])
        chunks.extend(ingested)
        offset_base += len(canonicalize_text(record_text).text) + 1

    return PreparedSource(
        source_key=key,
        source_type=source_type,
        source_title=source_title,
        source_hash=source_hash,
        source_url=source_url,
        record_count=len(records),
        chunks=tuple(chunks),
    )
