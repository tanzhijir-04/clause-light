"""数据库模型测试"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from server.models.database import (
    Analysis,
    ClauseAnalysis,
    Contract,
    KnowledgeRule,
    LegalReference,
    SyncLog,
    async_session_factory,
    migrate_schema,
    Base,
    WorkerRiskResult,
)


class TestContractModel:
    """合同模型测试"""

    async def test_create_contract(self, db_session):
        """测试创建合同"""
        contract = Contract(
            id="test_contract_1",
            title="测试租赁合同",
            type="租赁合同",
            source_file="/path/to/file.pdf",
        )
        db_session.add(contract)
        await db_session.commit()

        result = await db_session.execute(select(Contract).where(Contract.id == "test_contract_1"))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.title == "测试租赁合同"
        assert fetched.type == "租赁合同"
        assert fetched.source_file == "/path/to/file.pdf"
        assert fetched.created_at is not None

    async def test_contract_default_values(self, db_session):
        """测试合同默认值"""
        contract = Contract(id="test_contract_2")
        db_session.add(contract)
        await db_session.commit()

        result = await db_session.execute(select(Contract).where(Contract.id == "test_contract_2"))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.title == ""
        assert fetched.type == "其他"


class TestAnalysisModel:
    """分析结果模型测试"""

    async def test_create_analysis(self, db_session):
        """测试创建分析结果"""
        analysis = Analysis(
            id="test_analysis_1",
            contract_id="test_contract_1",
            model_used="deepseek-chat",
            overall_score=85,
            summary="合同风险可控",
            recommendation="sign",
            source="local",
        )
        db_session.add(analysis)
        await db_session.commit()

        result = await db_session.execute(select(Analysis).where(Analysis.id == "test_analysis_1"))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.overall_score == 85
        assert fetched.recommendation == "sign"


class TestClauseAnalysisModel:
    """条款分析模型测试"""

    async def test_create_clause_analysis(self, db_session):
        """测试创建条款分析"""
        clause = ClauseAnalysis(
            id="test_clause_1",
            analysis_id="test_analysis_1",
            clause_number="第一条",
            clause_title="合同目的",
            clause_content="本合同旨在...",
            risk_level="green",
            risk_type="无风险",
            risk_summary="正常条款",
            plain_explanation="这是一个正常的合同条款",
            legal_basis="《合同法》相关规定",
            severity_score=1,
            can_negotiate=False,
        )
        db_session.add(clause)
        await db_session.commit()

        result = await db_session.execute(
            select(ClauseAnalysis).where(ClauseAnalysis.id == "test_clause_1")
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.risk_level == "green"
        assert fetched.severity_score == 1


class TestKnowledgeRuleModel:
    """知识库规则模型测试"""

    async def test_create_knowledge_rule(self, db_session):
        """测试创建知识库规则"""
        rule = KnowledgeRule(
            id="test_rule_1",
            category="租赁",
            rule_text="租赁合同中违约金不应超过合同总金额的30%",
            trigger_keywords='["违约金", "租赁"]',
            confidence=0.8,
            source="manual",
            is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()

        result = await db_session.execute(
            select(KnowledgeRule).where(KnowledgeRule.id == "test_rule_1")
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.confidence == 0.8
        assert fetched.is_active is True

    async def test_knowledge_rule_inactive(self, db_session):
        """测试禁用的规则"""
        rule = KnowledgeRule(
            id="test_rule_2",
            category="劳动",
            rule_text="劳动合同测试规则",
            is_active=False,
        )
        db_session.add(rule)
        await db_session.commit()

        result = await db_session.execute(
            select(KnowledgeRule).where(KnowledgeRule.id == "test_rule_2")
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.is_active is False


class TestSchemaMigration:
    """旧库迁移测试：新分支新增列必须补齐，create_all 不会改已有表"""

    async def test_migrate_adds_status_column_to_legacy_knowledge_rules(self, tmp_path):
        """旧版 knowledge_rules 表缺少 status 列时，迁移后应补齐并回填状态"""
        db_file = tmp_path / "legacy.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")

        # 构造旧版 knowledge_rules 表（无 status 列）
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE knowledge_rules (
                    id VARCHAR PRIMARY KEY,
                    category VARCHAR NOT NULL,
                    rule_text TEXT NOT NULL,
                    trigger_keywords TEXT,
                    embedding TEXT,
                    confidence FLOAT,
                    source VARCHAR,
                    usage_count INTEGER,
                    confirm_count INTEGER,
                    reject_count INTEGER,
                    is_active BOOLEAN,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            await conn.execute(text(
                "INSERT INTO knowledge_rules (id, category, rule_text, is_active) VALUES ('r1', '通用', '测试规则', 1)"
            ))
            await conn.execute(text(
                "INSERT INTO knowledge_rules (id, category, rule_text, is_active) VALUES ('r2', '通用', '停用规则', 0)"
            ))

        try:
            await migrate_schema(engine)

            async with engine.connect() as conn:
                cols = {
                    row[1]
                    for row in (await conn.execute(text("PRAGMA table_info(knowledge_rules)"))).fetchall()
                }
            assert "status" in cols, "迁移后应存在 status 列"

            # 旧数据按 is_active 回填 status
            async with engine.connect() as conn:
                rows = {
                    r[0]: r[1]
                    for r in (await conn.execute(
                        text("SELECT id, status FROM knowledge_rules")
                    )).fetchall()
                }
            assert rows["r1"] == "active"
            assert rows["r2"] == "disabled"

            # ORM 全列查询可正常执行（迁移前会因缺少 status 列而报错）
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

            session_factory = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with session_factory() as session:
                result = await session.execute(
                    select(KnowledgeRule).order_by(KnowledgeRule.id)
                )
                rules = result.scalars().all()
            assert len(rules) == 2
            assert rules[0].status == "active"
        finally:
            await engine.dispose()

    async def test_migrate_adds_nullable_legal_reference_source_columns(self, tmp_path):
        """旧法规表迁移新增来源列，且不生成 DEFAULT None。"""
        db_file = tmp_path / "legacy-laws.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE legal_references (
                    id VARCHAR PRIMARY KEY,
                    law_name VARCHAR NOT NULL,
                    article_number VARCHAR,
                    content TEXT,
                    effective_date DATE,
                    tags TEXT
                )
            """))
        try:
            await migrate_schema(engine)
            async with engine.connect() as conn:
                columns = {
                    row[1]: row[4]
                    for row in (await conn.execute(text("PRAGMA table_info(legal_references)"))).fetchall()
                }
            assert columns["source_url"] is None
            assert columns["verified_at"] is None
        finally:
            await engine.dispose()

    async def test_migrate_adds_analysis_trace_fields_and_worker_table(self, tmp_path):
        db_file = tmp_path / "legacy-analysis.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE analyses (id VARCHAR PRIMARY KEY, contract_id VARCHAR NOT NULL)"))
            await conn.execute(text("CREATE TABLE clause_analyses (id VARCHAR PRIMARY KEY, analysis_id VARCHAR NOT NULL)"))
            await conn.execute(text("CREATE TABLE legal_references (id VARCHAR PRIMARY KEY, law_name VARCHAR NOT NULL)"))
            await conn.execute(text("INSERT INTO analyses (id, contract_id) VALUES ('a1', 'c1')"))
            await conn.execute(text("INSERT INTO clause_analyses (id, analysis_id) VALUES ('cl1', 'a1')"))
            await conn.run_sync(Base.metadata.create_all)
        try:
            await migrate_schema(engine)
            await migrate_schema(engine)
            async with engine.connect() as conn:
                analysis_columns = {row[1] for row in (await conn.execute(text("PRAGMA table_info(analyses)"))).fetchall()}
                clause_columns = {row[1] for row in (await conn.execute(text("PRAGMA table_info(clause_analyses)"))).fetchall()}
                analysis_row = (await conn.execute(text("SELECT status FROM analyses WHERE id='a1'"))).scalar_one()
                clause_row = (await conn.execute(text("SELECT analysis_status, review_required FROM clause_analyses WHERE id='cl1'"))).one()
                tables = {row[0] for row in (await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).fetchall()}
            assert {"status", "review_required", "review_reason", "processing_mode"} <= analysis_columns
            assert {"analysis_status", "review_required", "review_reason", "source_start", "source_end", "citation_ids"} <= clause_columns
            assert analysis_row == "completed"
            assert clause_row == ("completed", 0)
            assert "worker_risk_results" in tables
        finally:
            await engine.dispose()


class TestSyncLogModel:
    """同步日志模型测试"""

    async def test_create_sync_log(self, db_session):
        """测试创建同步日志"""
        log = SyncLog(
            id="test_log_1",
            sync_type="webdav",
            direction="push",
            status="success",
            details="上传完成",
        )
        db_session.add(log)
        await db_session.commit()

        result = await db_session.execute(select(SyncLog).where(SyncLog.id == "test_log_1"))
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.sync_type == "webdav"
        assert fetched.direction == "push"


class TestLegalReferenceModel:
    """法规条文模型测试"""

    async def test_create_legal_reference(self, db_session):
        """测试创建法规条文"""
        ref = LegalReference(
            id="test_ref_1",
            law_name="中华人民共和国民法典",
            article_number="第五百七十七条",
            content="当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。",
            tags='["合同违约", "损害赔偿"]',
        )
        db_session.add(ref)
        await db_session.commit()

        result = await db_session.execute(
            select(LegalReference).where(LegalReference.id == "test_ref_1")
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.law_name == "中华人民共和国民法典"
