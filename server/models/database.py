"""数据库模型 — SQLAlchemy 2.0 async ORM"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, date
from typing import AsyncGenerator

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
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from server.config import settings

logger = logging.getLogger(__name__)


# ── 基类 ──


class Base(DeclarativeBase):
    pass


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
    tags = Column(Text, nullable=True)  # JSON 字符串


class SyncLog(Base):
    """同步历史"""

    __tablename__ = "sync_log"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    sync_type = Column(String, nullable=False)  # webdav / git / s3
    direction = Column(String, nullable=False)  # push / pull
    status = Column(String, nullable=False)  # success / failed
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


# ── 数据库引擎 ──

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库初始化完成")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
