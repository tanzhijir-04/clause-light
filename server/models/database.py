"""数据库模型 — SQLAlchemy 2.0 async ORM"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
    inspect,
)
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401  兼容 v1 模块导入

from server.config import settings
from server.models.base import Base
from server.platform.database import async_session_factory, engine, get_db

logger = logging.getLogger(__name__)


# ── 模型 ──


class Contract(Base):
    """合同主表"""

    __tablename__ = "contracts"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    title = Column(String, nullable=False, default="")
    type = Column(String, nullable=False, default="其他")
    source_file = Column(String, nullable=True)
    ocr_text = Column(Text, nullable=True)
    ocr_raw = Column(Text, nullable=True)  # JSON 字符串
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Analysis(Base):
    """分析结果"""

    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    contract_id = Column(String, nullable=False)
    model_used = Column(String, nullable=True)
    overall_score = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    recommendation = Column(String, nullable=True)  # sign / negotiate_first / reject
    raw_result = Column(Text, nullable=True)  # JSON 字符串
    source = Column(String, nullable=True)  # local / cloud / remote_pc
    status = Column(String, default="completed")
    review_required = Column(Boolean, default=False)
    review_reason = Column(Text, nullable=True)
    processing_mode = Column(String, nullable=True)  # local / remote
    created_at = Column(DateTime, default=func.now())


class ClauseAnalysis(Base):
    """逐条分析"""

    __tablename__ = "clause_analyses"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    analysis_id = Column(String, nullable=False)
    clause_number = Column(String, nullable=True)
    clause_title = Column(String, nullable=True)
    clause_content = Column(Text, nullable=True)
    risk_level = Column(String, nullable=True)  # red / yellow / green
    risk_type = Column(String, nullable=True)
    risk_summary = Column(Text, nullable=True)
    plain_explanation = Column(Text, nullable=True)
    legal_basis = Column(Text, nullable=True)
    severity_score = Column(Integer, nullable=True)
    suggested_clause = Column(Text, nullable=True)
    can_negotiate = Column(Boolean, default=False)
    user_feedback = Column(String, nullable=True)  # correct / incorrect / null
    analysis_status = Column(String, default="completed")
    review_required = Column(Boolean, default=False)
    review_reason = Column(Text, nullable=True)
    source_start = Column(Integer, default=-1)
    source_end = Column(Integer, default=-1)
    citation_ids = Column(Text, nullable=True)  # JSON list
    created_at = Column(DateTime, default=func.now())


class KnowledgeRule(Base):
    """知识库规则"""

    __tablename__ = "knowledge_rules"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    category = Column(String, nullable=False, default="通用")
    rule_text = Column(Text, nullable=False)
    trigger_keywords = Column(Text, nullable=True)  # JSON 字符串
    embedding = Column(Text, nullable=True)  # 预留，暂不使用 BLOB
    confidence = Column(Float, default=0.5)
    source = Column(String, default="manual")  # manual / auto_learned / user_feedback
    usage_count = Column(Integer, default=0)
    confirm_count = Column(Integer, default=0)
    reject_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    # pending|active|disabled|rolled_back；检索以 status 为准，is_active 为兼容字段
    status = Column(String, default="active")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class LegalReference(Base):
    """法规条文"""

    __tablename__ = "legal_references"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    law_name = Column(String, nullable=False)
    article_number = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    effective_date = Column(Date, nullable=True)
    source_url = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    tags = Column(Text, nullable=True)  # JSON 字符串


class WorkerRiskResult(Base):
    """不可变的 Worker 输出轨迹；冲突复核以新行追加。"""

    __tablename__ = "worker_risk_results"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    analysis_id = Column(String, nullable=False, index=True)
    clause_number = Column(String, nullable=True, index=True)
    dimension = Column(String, nullable=False)
    phase = Column(String, nullable=False, default="initial")
    risk_level = Column(String, nullable=True)
    risk_type = Column(String, nullable=True)
    issue = Column(Text, nullable=True)
    unfavorable_to = Column(String, nullable=True)
    severity_score = Column(Integer, nullable=True)
    suggestion = Column(Text, nullable=True)
    legal_basis = Column(Text, nullable=True)
    citation_ids = Column(Text, nullable=True)
    analysis_status = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    review_required = Column(Boolean, default=False)
    review_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class SyncLog(Base):
    """同步历史"""

    __tablename__ = "sync_log"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    sync_type = Column(String, nullable=False)  # webdav / git / s3
    direction = Column(String, nullable=False)  # push / pull
    status = Column(String, nullable=False)  # success / failed
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


# ── 分层记忆 L0–L3 ──


class MemorySession(Base):
    """L0 记忆会话"""

    __tablename__ = "memory_sessions"

    id = Column(String, primary_key=True)
    contract_id = Column(String, nullable=True)
    contract_type = Column(String, nullable=True)
    status = Column(String, default="open")  # open|closed
    owner_user_id = Column(String, default="local")
    created_at = Column(DateTime, default=func.now())
    closed_at = Column(DateTime, nullable=True)


class MemoryEvent(Base):
    """L0 记忆事件流"""

    __tablename__ = "memory_events"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # step|feedback|tool|system
    payload = Column(Text, nullable=False)  # JSON
    created_at = Column(DateTime, default=func.now())


class MemoryAtom(Base):
    """L1 记忆原子（事实/偏好/约束）"""

    __tablename__ = "memory_atoms"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    kind = Column(String, default="fact")  # fact|preference|constraint|event
    contract_type = Column(String, nullable=True)
    confidence = Column(Float, default=0.5)
    status = Column(String, default="pending")  # pending|active|disabled|rolled_back
    embedding = Column(Text, nullable=True)
    confirm_count = Column(Integer, default=0)
    reject_count = Column(Integer, default=0)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")  # private|team|restricted
    acl_json = Column(Text, nullable=True)  # JSON list of grants
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class MemoryScenario(Base):
    """L2 情景记忆"""

    __tablename__ = "memory_scenarios"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    contract_type = Column(String, nullable=True)
    atom_ids = Column(Text, nullable=True)  # JSON list
    confidence = Column(Float, default=0.5)
    status = Column(String, default="pending")
    embedding = Column(Text, nullable=True)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")
    acl_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class MemoryPersona(Base):
    """L3 人格/长期偏好画像"""

    __tablename__ = "memory_personas"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    confidence = Column(Float, default=0.5)
    status = Column(String, default="pending")
    embedding = Column(Text, nullable=True)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")
    acl_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ── 自进化资产：Skill / Wiki / 审计 ──


class Skill(Base):
    """结构化审查 Skill 资产"""

    __tablename__ = "skills"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    name = Column(String, nullable=False)
    version = Column(Integer, default=1)
    status = Column(String, default="pending")  # pending|active|disabled|rolled_back
    triggers = Column(Text, nullable=True)  # JSON: contract_types / keywords
    steps = Column(Text, nullable=True)  # JSON list
    validation = Column(Text, nullable=True)  # JSON list
    resources = Column(Text, nullable=True)  # JSON list
    confidence = Column(Float, default=0.5)
    embedding = Column(Text, nullable=True)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")
    acl_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class WikiPage(Base):
    """本地 Wiki 页面"""

    __tablename__ = "wiki_pages"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    slug = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    status = Column(String, default="pending")  # pending|active|disabled|rolled_back
    source = Column(String, default="manual")  # manual|import|distill
    confidence = Column(Float, default=0.5)
    embedding = Column(Text, nullable=True)
    owner_user_id = Column(String, default="local")
    visibility = Column(String, default="private")
    acl_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class WikiLink(Base):
    """Wiki 页面间链接"""

    __tablename__ = "wiki_links"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    from_page_id = Column(String, nullable=False, index=True)
    to_page_id = Column(String, nullable=False, index=True)
    rel = Column(String, default="related")  # cites|related|supersedes
    created_at = Column(DateTime, default=func.now())


class AssetAuditLog(Base):
    """资产状态变更审计日志"""

    __tablename__ = "asset_audit_log"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    asset_type = Column(String, nullable=False)  # rule|atom|skill|wiki
    asset_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # create|activate|approve|reject|rollback
    detail = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=func.now())


async def init_db() -> None:
    """创建所有表，并补齐已有表的新增列"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_schema(engine)
    logger.info("数据库初始化完成")


# ── 轻量迁移 ──

# 新分支在已有表上新增的列（create_all 不会修改已有表，需手动 ALTER）
_LEGACY_COLUMN_MIGRATIONS: dict[str, list[tuple[str, str, object | None]]] = {
    "analyses": [
        ("status", "VARCHAR", "completed"),
        ("review_required", "BOOLEAN", False),
        ("review_reason", "TEXT", None),
        ("processing_mode", "VARCHAR", None),
    ],
    "clause_analyses": [
        ("analysis_status", "VARCHAR", "completed"),
        ("review_required", "BOOLEAN", False),
        ("review_reason", "TEXT", None),
        ("source_start", "INTEGER", -1),
        ("source_end", "INTEGER", -1),
        ("citation_ids", "TEXT", None),
    ],
    "knowledge_rules": [("status", "VARCHAR", "active")],
    "legal_references": [
        ("source_url", "TEXT", None),
        ("verified_at", "DATETIME", None),
    ],
}


async def migrate_schema(engine) -> None:
    """为已有表补齐新分支新增的列（幂等），并回填兼容字段"""

    def _run(sync_conn) -> None:
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        for table_name, migrations in _LEGACY_COLUMN_MIGRATIONS.items():
            if table_name not in tables:
                continue
            columns = {c["name"] for c in inspector.get_columns(table_name)}
            for col_name, col_type, default in migrations:
                if col_name in columns:
                    continue
                default_sql = ""
                if default is not None:
                    if isinstance(default, str):
                        default_sql = f" DEFAULT '{default}'"
                    elif isinstance(default, bool):
                        default_sql = f" DEFAULT {'1' if default else '0'}"
                    else:
                        default_sql = f" DEFAULT {default}"
                sync_conn.exec_driver_sql(
                    f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {col_type}{default_sql}'
                )
                logger.info("数据库迁移: %s 表新增列 %s", table_name, col_name)
                if table_name == "knowledge_rules" and col_name == "status":
                    # 旧数据按 is_active 回填 status
                    sync_conn.exec_driver_sql(
                        "UPDATE knowledge_rules SET status = "
                        "CASE WHEN is_active THEN 'active' ELSE 'disabled' END"
                    )
                columns.add(col_name)

    async with engine.begin() as conn:
        await conn.run_sync(_run)
