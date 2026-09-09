"""v1 SQLite 到 ContractOps 模型的只读、幂等导入器。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.database import (
    Analysis,
    AssetAuditLog,
    ClauseAnalysis,
    Contract as LegacyContract,
    KnowledgeRule,
    LegalReference,
    MemoryAtom,
    MemoryEvent,
    MemoryPersona,
    MemoryScenario,
    MemorySession,
    Skill,
    SyncLog,
    WikiLink,
    WikiPage,
    WorkerRiskResult,
)
from server.modules.contracts.models import Contract, ContractVersion
from server.modules.legacy_import.models import ImportBatch, LegacyIdMap
from server.modules.tenancy.models import Organization


SOURCE_TABLES = (
    "contracts",
    "analyses",
    "clause_analyses",
    "knowledge_rules",
    "legal_references",
    "memory_sessions",
    "memory_events",
    "memory_atoms",
    "memory_scenarios",
    "memory_personas",
    "skills",
    "wiki_pages",
    "wiki_links",
    "asset_audit_log",
    "sync_log",
    "worker_risk_results",
)


@dataclass(frozen=True)
class ImportReport:
    batch_id: uuid.UUID | None
    status: str
    source_counts: dict[str, int]
    written_counts: dict[str, int]
    rejected_rows: list[dict[str, str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_id": str(self.batch_id) if self.batch_id else None,
            "status": self.status,
            "source_counts": self.source_counts,
            "written_counts": self.written_counts,
            "rejected_rows": self.rejected_rows,
        }


def source_sha256(path: Path) -> str:
    """计算源文件摘要。"""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_readonly(path: Path) -> sqlite3.Connection:
    """以 SQLite URI 只读打开源库。"""
    resolved = path.resolve(strict=True)
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


class LegacyImporter:
    """执行源库扫描、映射、校验和重复导入保护。"""

    def __init__(self, session: AsyncSession, organization_name: str = "ClauseLight v1 Import") -> None:
        self.session = session
        self.organization_name = organization_name
        self.source_counts: dict[str, int] = {table: 0 for table in SOURCE_TABLES}
        self.written_counts: dict[str, int] = {table: 0 for table in SOURCE_TABLES}
        self.rejected_rows: list[dict[str, str]] = []
        self.maps: dict[str, dict[str, uuid.UUID]] = {}
        self.batch: ImportBatch | None = None
        self.organization_id: uuid.UUID | None = None

    async def run(self, source_path: Path, *, dry_run: bool = False) -> ImportReport:
        """运行导入；dry-run 只读取源库并生成计数。"""
        source_path = Path(source_path)
        digest = source_sha256(source_path)
        with open_readonly(source_path) as source:
            rows = self._read_source(source)

        if not dry_run:
            existing = await self.session.scalar(
                select(ImportBatch).where(ImportBatch.source_sha256 == digest)
            )
            if existing is not None:
                return self._report_from_batch(existing)
            self.batch = ImportBatch(source_sha256=digest, status="running", counts={})
            self.session.add(self.batch)
            await self.session.flush()

        await self._prepare_organization()
        await self._import_rows(rows)
        status = self._status()
        report = ImportReport(
            batch_id=self.batch.id if self.batch is not None else None,
            status=status,
            source_counts=dict(self.source_counts),
            written_counts=dict(self.written_counts),
            rejected_rows=list(self.rejected_rows),
        )
        if self.batch is not None:
            self.batch.status = status
            self.batch.counts = report.as_dict()
            await self.session.flush()
        return report

    def _read_source(self, source: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
        tables = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        result: dict[str, list[dict[str, Any]]] = {}
        for table in SOURCE_TABLES:
            if table not in tables:
                result[table] = []
                continue
            rows = [dict(row) for row in source.execute(f'SELECT * FROM "{table}"')]
            result[table] = rows
            self.source_counts[table] = len(rows)
        return result

    async def _prepare_organization(self) -> None:
        slug = "clauselight-v1-import"
        if self.batch is None:
            self.organization_id = uuid.uuid5(uuid.NAMESPACE_URL, f"org:{slug}")
            return
        organization = await self.session.scalar(
            select(Organization).where(Organization.slug == slug)
        )
        if organization is None:
            organization = Organization(name=self.organization_name, slug=slug)
            self.session.add(organization)
            await self.session.flush()
        self.organization_id = organization.id
        self.maps.setdefault("organization", {})["default"] = organization.id
        await self._record_map("organization", "default", organization.id)

    async def _import_rows(self, rows: dict[str, list[dict[str, Any]]]) -> None:
        await self._import_contracts(rows["contracts"])
        await self._import_analyses(rows["analyses"])
        await self._import_clause_analyses(rows["clause_analyses"])
        await self._import_knowledge_rules(rows["knowledge_rules"])
        await self._import_legal_references(rows["legal_references"])
        await self._import_memory_sessions(rows["memory_sessions"])
        await self._import_memory_events(rows["memory_events"])
        await self._import_memory_atoms(rows["memory_atoms"])
        await self._import_memory_scenarios(rows["memory_scenarios"])
        await self._import_memory_personas(rows["memory_personas"])
        await self._import_skills(rows["skills"])
        await self._import_wiki_pages(rows["wiki_pages"])
        await self._import_wiki_links(rows["wiki_links"])
        await self._import_asset_audit(rows["asset_audit_log"])
        await self._import_sync_logs(rows["sync_log"])
        await self._import_worker_results(rows["worker_risk_results"])

    async def _import_contracts(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if not legacy_id or self.organization_id is None:
                self._reject("contracts", legacy_id, "INVALID_SOURCE_ID")
                continue
            new_id = self._stable_id("contract", legacy_id)
            version_id = self._stable_id("contract_version", legacy_id)
            self.maps.setdefault("contract", {})[legacy_id] = new_id
            self.maps.setdefault("contract_version", {})[legacy_id] = version_id
            if self.batch is not None:
                if await self.session.get(Contract, new_id) is None:
                    self.session.add(
                        Contract(
                            id=new_id,
                            organization_id=self.organization_id,
                            title=str(row.get("title") or "未命名合同"),
                            contract_type=str(row.get("type") or "other"),
                        )
                    )
                normalized = str(row.get("ocr_text") or "").replace("\r\n", "\n").strip()
                if await self.session.get(ContractVersion, version_id) is None:
                    self.session.add(
                        ContractVersion(
                            id=version_id,
                            organization_id=self.organization_id,
                            contract_id=new_id,
                            version_number=1,
                            text_content=normalized,
                            content_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                        )
                    )
                if await self.session.get(LegacyContract, legacy_id) is None:
                    self.session.add(
                        LegacyContract(
                            id=legacy_id,
                            title=str(row.get("title") or ""),
                            type=str(row.get("type") or "其他"),
                            source_file=row.get("source_file"),
                            ocr_text=row.get("ocr_text"),
                            ocr_raw=row.get("ocr_raw"),
                        )
                    )
                await self._record_map("contract", legacy_id, new_id)
                await self._record_map("contract_version", legacy_id, version_id)
            self.written_counts["contracts"] += 1

    async def _import_analyses(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            contract_id = str(row.get("contract_id") or "")
            if contract_id not in self.maps.get("contract", {}):
                self._reject("analyses", legacy_id, "MISSING_CONTRACT")
                continue
            self.maps.setdefault("analysis", {})[legacy_id] = self._stable_id("analysis", legacy_id)
            if self.batch is not None and await self.session.get(Analysis, legacy_id) is None:
                self.session.add(
                    Analysis(
                        id=legacy_id,
                        contract_id=contract_id,
                        model_used=row.get("model_used"),
                        overall_score=row.get("overall_score"),
                        summary=row.get("summary"),
                        recommendation=row.get("recommendation"),
                        raw_result=row.get("raw_result"),
                        source=row.get("source"),
                        status=row.get("status") or "completed",
                        review_required=bool(row.get("review_required", False)),
                        review_reason=row.get("review_reason"),
                        processing_mode=row.get("processing_mode"),
                    )
                )
                await self._record_map("analysis", legacy_id, self.maps["analysis"][legacy_id])
            self.written_counts["analyses"] += 1

    async def _import_clause_analyses(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            analysis_id = str(row.get("analysis_id") or "")
            if analysis_id not in self.maps.get("analysis", {}):
                self._reject("clause_analyses", legacy_id, "MISSING_ANALYSIS")
                continue
            if self.batch is not None and await self.session.get(ClauseAnalysis, legacy_id) is None:
                self.session.add(
                    ClauseAnalysis(
                        id=legacy_id,
                        analysis_id=analysis_id,
                        clause_number=row.get("clause_number"),
                        clause_title=row.get("clause_title"),
                        clause_content=row.get("clause_content"),
                        risk_level=row.get("risk_level"),
                        risk_type=row.get("risk_type"),
                        risk_summary=row.get("risk_summary"),
                        plain_explanation=row.get("plain_explanation"),
                        legal_basis=row.get("legal_basis"),
                        severity_score=row.get("severity_score"),
                        suggested_clause=row.get("suggested_clause"),
                        can_negotiate=bool(row.get("can_negotiate", False)),
                        user_feedback=row.get("user_feedback"),
                        analysis_status=row.get("analysis_status") or "completed",
                        review_required=bool(row.get("review_required", False)),
                        review_reason=row.get("review_reason"),
                        source_start=row.get("source_start", -1),
                        source_end=row.get("source_end", -1),
                        citation_ids=row.get("citation_ids"),
                    )
                )
            self.written_counts["clause_analyses"] += 1

    async def _import_knowledge_rules(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if not legacy_id:
                self._reject("knowledge_rules", legacy_id, "INVALID_SOURCE_ID")
                continue
            self.maps.setdefault("rule", {})[legacy_id] = self._stable_id("rule", legacy_id)
            if self.batch is not None and await self.session.get(KnowledgeRule, legacy_id) is None:
                self.session.add(
                    KnowledgeRule(
                        id=legacy_id,
                        category=row.get("category") or "通用",
                        rule_text=row.get("rule_text") or "",
                        trigger_keywords=row.get("trigger_keywords"),
                        embedding=row.get("embedding"),
                        confidence=row.get("confidence", 0.5),
                        source=row.get("source") or "manual",
                        usage_count=row.get("usage_count", 0),
                        confirm_count=row.get("confirm_count", 0),
                        reject_count=row.get("reject_count", 0),
                        is_active=bool(row.get("is_active", True)),
                        status=row.get("status") or ("active" if row.get("is_active", True) else "disabled"),
                    )
                )
                await self._record_map("rule", legacy_id, self.maps["rule"][legacy_id])
            self.written_counts["knowledge_rules"] += 1

    async def _import_legal_references(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if not legacy_id:
                self._reject("legal_references", legacy_id, "INVALID_SOURCE_ID")
                continue
            if self.batch is not None and await self.session.get(LegalReference, legacy_id) is None:
                self.session.add(
                    LegalReference(
                        id=legacy_id,
                        law_name=row.get("law_name") or "",
                        article_number=row.get("article_number"),
                        content=row.get("content"),
                        tags=row.get("tags"),
                        source_url=row.get("source_url"),
                        verified_at=None,
                    )
                )
                await self._record_map("legal_reference", legacy_id, self._stable_id("legal_reference", legacy_id))
            self.written_counts["legal_references"] += 1

    async def _import_memory_sessions(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            self.maps.setdefault("memory_session", {})[legacy_id] = self._stable_id("memory_session", legacy_id)
            if self.batch is not None and await self.session.get(MemorySession, legacy_id) is None:
                self.session.add(
                    MemorySession(
                        id=legacy_id,
                        contract_id=row.get("contract_id"),
                        contract_type=row.get("contract_type"),
                        status=row.get("status") or "open",
                        owner_user_id=row.get("owner_user_id") or "local",
                    )
                )
                await self._record_map("memory_session", legacy_id, self.maps["memory_session"][legacy_id])
            self.written_counts["memory_sessions"] += 1

    async def _import_memory_events(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if str(row.get("session_id") or "") not in self.maps.get("memory_session", {}):
                self._reject("memory_events", legacy_id, "MISSING_SESSION")
                continue
            if self.batch is not None and await self.session.get(MemoryEvent, legacy_id) is None:
                self.session.add(
                    MemoryEvent(
                        id=legacy_id,
                        session_id=row.get("session_id"),
                        event_type=row.get("event_type") or "system",
                        payload=row.get("payload") or "{}",
                    )
                )
            self.written_counts["memory_events"] += 1

    async def _import_memory_atoms(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            session_id = row.get("session_id")
            if session_id and str(session_id) not in self.maps.get("memory_session", {}):
                self._reject("memory_atoms", legacy_id, "MISSING_SESSION")
                continue
            self.maps.setdefault("atom", {})[legacy_id] = self._stable_id("atom", legacy_id)
            if self.batch is not None and await self.session.get(MemoryAtom, legacy_id) is None:
                self.session.add(
                    MemoryAtom(
                        id=legacy_id,
                        session_id=session_id,
                        content=row.get("content") or "",
                        kind=row.get("kind") or "fact",
                        contract_type=row.get("contract_type"),
                        confidence=row.get("confidence", 0.5),
                        status=row.get("status") or "pending",
                        embedding=row.get("embedding"),
                        owner_user_id=row.get("owner_user_id") or "local",
                        visibility=row.get("visibility") or "private",
                        acl_json=row.get("acl_json"),
                    )
                )
                await self._record_map("atom", legacy_id, self.maps["atom"][legacy_id])
            self.written_counts["memory_atoms"] += 1

    async def _import_memory_scenarios(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            self.maps.setdefault("scenario", {})[legacy_id] = self._stable_id("scenario", legacy_id)
            if self.batch is not None and await self.session.get(MemoryScenario, legacy_id) is None:
                self.session.add(
                    MemoryScenario(
                        id=legacy_id,
                        title=row.get("title") or "",
                        summary=row.get("summary") or "",
                        contract_type=row.get("contract_type"),
                        atom_ids=row.get("atom_ids"),
                        confidence=row.get("confidence", 0.5),
                        status=row.get("status") or "pending",
                        embedding=row.get("embedding"),
                        owner_user_id=row.get("owner_user_id") or "local",
                        visibility=row.get("visibility") or "private",
                        acl_json=row.get("acl_json"),
                    )
                )
                await self._record_map("scenario", legacy_id, self.maps["scenario"][legacy_id])
            self.written_counts["memory_scenarios"] += 1

    async def _import_memory_personas(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            self.maps.setdefault("persona", {})[legacy_id] = self._stable_id("persona", legacy_id)
            if self.batch is not None and await self.session.get(MemoryPersona, legacy_id) is None:
                self.session.add(
                    MemoryPersona(
                        id=legacy_id,
                        title=row.get("title") or "",
                        summary=row.get("summary") or "",
                        confidence=row.get("confidence", 0.5),
                        status=row.get("status") or "pending",
                        embedding=row.get("embedding"),
                        owner_user_id=row.get("owner_user_id") or "local",
                        visibility=row.get("visibility") or "private",
                        acl_json=row.get("acl_json"),
                    )
                )
                await self._record_map("persona", legacy_id, self.maps["persona"][legacy_id])
            self.written_counts["memory_personas"] += 1

    async def _import_skills(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            self.maps.setdefault("skill", {})[legacy_id] = self._stable_id("skill", legacy_id)
            if self.batch is not None and await self.session.get(Skill, legacy_id) is None:
                self.session.add(
                    Skill(
                        id=legacy_id,
                        name=row.get("name") or "",
                        version=row.get("version", 1),
                        status=row.get("status") or "pending",
                        triggers=row.get("triggers"),
                        steps=row.get("steps"),
                        validation=row.get("validation"),
                        resources=row.get("resources"),
                        confidence=row.get("confidence", 0.5),
                        embedding=row.get("embedding"),
                        owner_user_id=row.get("owner_user_id") or "local",
                        visibility=row.get("visibility") or "private",
                        acl_json=row.get("acl_json"),
                    )
                )
                await self._record_map("skill", legacy_id, self.maps["skill"][legacy_id])
            self.written_counts["skills"] += 1

    async def _import_wiki_pages(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            self.maps.setdefault("wiki", {})[legacy_id] = self._stable_id("wiki", legacy_id)
            if self.batch is not None and await self.session.get(WikiPage, legacy_id) is None:
                self.session.add(
                    WikiPage(
                        id=legacy_id,
                        slug=row.get("slug") or legacy_id,
                        title=row.get("title") or "",
                        body=row.get("body") or "",
                        status=row.get("status") or "pending",
                        source=row.get("source"),
                        confidence=row.get("confidence", 0.5),
                        embedding=row.get("embedding"),
                        owner_user_id=row.get("owner_user_id") or "local",
                        visibility=row.get("visibility") or "private",
                        acl_json=row.get("acl_json"),
                    )
                )
                await self._record_map("wiki", legacy_id, self.maps["wiki"][legacy_id])
            self.written_counts["wiki_pages"] += 1

    async def _import_wiki_links(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if str(row.get("from_page_id") or "") not in self.maps.get("wiki", {}) or str(
                row.get("to_page_id") or ""
            ) not in self.maps.get("wiki", {}):
                self._reject("wiki_links", legacy_id, "MISSING_WIKI_PAGE")
                continue
            if self.batch is not None and await self.session.get(WikiLink, legacy_id) is None:
                self.session.add(
                    WikiLink(
                        id=legacy_id,
                        from_page_id=row.get("from_page_id"),
                        to_page_id=row.get("to_page_id"),
                        rel=row.get("rel") or "related",
                    )
                )
            self.written_counts["wiki_links"] += 1

    async def _import_asset_audit(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if self.batch is not None and await self.session.get(AssetAuditLog, legacy_id) is None:
                self.session.add(
                    AssetAuditLog(
                        id=legacy_id,
                        asset_type=row.get("asset_type") or "unknown",
                        asset_id=row.get("asset_id") or "",
                        action=row.get("action") or "create",
                        detail=row.get("detail"),
                    )
                )
            self.written_counts["asset_audit_log"] += 1

    async def _import_sync_logs(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if self.batch is not None and await self.session.get(SyncLog, legacy_id) is None:
                self.session.add(
                    SyncLog(
                        id=legacy_id,
                        sync_type=row.get("sync_type") or "unknown",
                        direction=row.get("direction") or "unknown",
                        status=row.get("status") or "unknown",
                        details=row.get("details"),
                    )
                )
            self.written_counts["sync_log"] += 1

    async def _import_worker_results(self, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            legacy_id = str(row.get("id") or "")
            if self.batch is not None and await self.session.get(WorkerRiskResult, legacy_id) is None:
                self.session.add(
                    WorkerRiskResult(
                        id=legacy_id,
                        analysis_id=row.get("analysis_id") or "",
                        clause_number=row.get("clause_number"),
                        dimension=row.get("dimension") or "unknown",
                        phase=row.get("phase") or "initial",
                        risk_level=row.get("risk_level"),
                        risk_type=row.get("risk_type"),
                        issue=row.get("issue"),
                        unfavorable_to=row.get("unfavorable_to"),
                        severity_score=row.get("severity_score"),
                        suggestion=row.get("suggestion"),
                        legal_basis=row.get("legal_basis"),
                        citation_ids=row.get("citation_ids"),
                        analysis_status=row.get("analysis_status"),
                        failure_reason=row.get("failure_reason"),
                        review_required=bool(row.get("review_required", False)),
                        review_reason=row.get("review_reason"),
                    )
                )
            self.written_counts["worker_risk_results"] += 1

    async def _record_map(self, entity_type: str, legacy_id: str, new_id: uuid.UUID) -> None:
        if self.batch is None:
            return
        existing = await self.session.scalar(
            select(LegacyIdMap).where(
                LegacyIdMap.batch_id == self.batch.id,
                LegacyIdMap.entity_type == entity_type,
                LegacyIdMap.legacy_id == legacy_id,
            )
        )
        if existing is None:
            self.session.add(
                LegacyIdMap(
                    batch_id=self.batch.id,
                    entity_type=entity_type,
                    legacy_id=legacy_id,
                    new_id=new_id,
                )
            )

    def _stable_id(self, entity_type: str, legacy_id: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"clauselight:v1:{entity_type}:{legacy_id}")

    def _reject(self, entity_type: str, legacy_id: str, error_code: str) -> None:
        self.rejected_rows.append(
            {"entity_type": entity_type, "legacy_id": legacy_id, "error_code": error_code}
        )

    def _status(self) -> str:
        conserved = all(
            self.source_counts[table]
            == self.written_counts[table]
            + sum(1 for row in self.rejected_rows if row["entity_type"] == table)
            for table in SOURCE_TABLES
        )
        return "completed" if conserved else "failed"

    def _report_from_batch(self, batch: ImportBatch) -> ImportReport:
        counts = batch.counts or {}
        return ImportReport(
            batch_id=batch.id,
            status=batch.status,
            source_counts=dict(counts.get("source_counts", {})),
            written_counts=dict(counts.get("written_counts", {})),
            rejected_rows=list(counts.get("rejected_rows", [])),
        )
