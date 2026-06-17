"""知识库引擎 — 规则管理与检索"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import TYPE_CATEGORY_MAP
from server.models.database import (
    Analysis,
    ClauseAnalysis,
    Contract,
    KnowledgeRule,
    LegalReference,
)

logger = logging.getLogger(__name__)


class KnowledgeEngine:
    """知识库管理与检索"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        query: str,
        contract_type: str,
        top_k: int = 5,
    ) -> list[str]:
        """
        检索相关规则。

        1. 查询 is_active=1 的规则
        2. 按 category 过滤（通用 + 对应合同类型）
        3. 关键词匹配
        4. 按 confidence 降序排序
        5. 返回 Top K 条规则文本
        """
        category = TYPE_CATEGORY_MAP.get(contract_type, "其他")

        stmt = select(KnowledgeRule).where(KnowledgeRule.is_active == True)  # noqa: E712
        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        matched: list[tuple[KnowledgeRule, float]] = []
        query_lower = query.lower()

        for rule in rules:
            # 类别匹配：通用规则始终包含，专业规则按类型过滤
            if rule.category != "通用" and rule.category != category:
                continue

            # 关键词匹配评分
            score = 0.0
            rule_lower = rule.rule_text.lower()
            if query_lower in rule_lower:
                score += 2.0

            # 触发关键词匹配
            if rule.trigger_keywords:
                try:
                    keywords = json.loads(rule.trigger_keywords)
                    for kw in keywords:
                        if kw.lower() in query_lower:
                            score += 1.0
                except (json.JSONDecodeError, TypeError):
                    pass

            if score > 0:
                matched.append((rule, score + rule.confidence))

        # 按综合得分降序排序
        matched.sort(key=lambda x: x[1], reverse=True)

        # 更新使用次数
        for rule, _ in matched[:top_k]:
            rule.usage_count = (rule.usage_count or 0) + 1

        return [rule.rule_text for rule, _ in matched[:top_k]]

    async def add_rule(self, rule_data: dict) -> dict:
        """新增规则"""
        rule = KnowledgeRule(
            id=uuid.uuid4().hex,
            category=rule_data.get("category", "通用"),
            rule_text=rule_data["rule_text"],
            trigger_keywords=json.dumps(rule_data.get("trigger_keywords", []), ensure_ascii=False),
            confidence=rule_data.get("confidence", 0.5),
            source=rule_data.get("source", "manual"),
        )
        self.db.add(rule)
        await self.db.flush()
        logger.info("新增规则: id=%s category=%s", rule.id, rule.category)
        return {"id": rule.id, "success": True}

    async def update_rule(self, rule_id: str, data: dict) -> None:
        """更新规则"""
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == rule_id)
        result = await self.db.execute(stmt)
        rule = result.scalar_one_or_none()
        if not rule:
            return

        if "category" in data:
            rule.category = data["category"]
        if "rule_text" in data:
            rule.rule_text = data["rule_text"]
        if "confidence" in data:
            rule.confidence = data["confidence"]
        if "is_active" in data:
            rule.is_active = data["is_active"]
        if "trigger_keywords" in data:
            rule.trigger_keywords = json.dumps(data["trigger_keywords"], ensure_ascii=False)

        rule.updated_at = datetime.now(timezone.utc)
        logger.info("更新规则: id=%s", rule_id)

    async def delete_rule(self, rule_id: str) -> None:
        """删除规则"""
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == rule_id)
        result = await self.db.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule:
            await self.db.delete(rule)
            logger.info("删除规则: id=%s", rule_id)

    async def get_stats(self) -> dict:
        """获取仪表盘统计数据"""
        # 规则总数
        count_stmt = select(func.count()).select_from(KnowledgeRule)
        total_rules = (await self.db.execute(count_stmt)).scalar() or 0

        # 平均置信度
        avg_stmt = select(func.avg(KnowledgeRule.confidence)).select_from(KnowledgeRule)
        avg_confidence = (await self.db.execute(avg_stmt)).scalar() or 0.0

        # 法规条文数
        law_stmt = select(func.count()).select_from(LegalReference)
        total_laws = (await self.db.execute(law_stmt)).scalar() or 0

        # 待审核数（confidence < 0.7 且 source 为 auto_learned）
        pending_stmt = (
            select(func.count())
            .select_from(KnowledgeRule)
            .where(KnowledgeRule.source == "auto_learned")
            .where(KnowledgeRule.confidence < 0.7)
        )
        pending = (await self.db.execute(pending_stmt)).scalar() or 0

        # 合同总数
        contract_count_stmt = select(func.count()).select_from(Contract)
        total_contracts = (await self.db.execute(contract_count_stmt)).scalar() or 0

        # 本月新增合同数
        now = datetime.now(timezone.utc)
        month_stmt = (
            select(func.count())
            .select_from(Contract)
            .where(extract("year", Contract.created_at) == now.year)
            .where(extract("month", Contract.created_at) == now.month)
        )
        this_month = (await self.db.execute(month_stmt)).scalar() or 0

        # 平均风险分
        avg_score_stmt = select(func.avg(Analysis.overall_score)).select_from(Analysis)
        avg_score = (await self.db.execute(avg_score_stmt)).scalar() or 0.0

        # 高/中/低风险条款数
        red_stmt = (
            select(func.count())
            .select_from(ClauseAnalysis)
            .where(ClauseAnalysis.risk_level == "red")
        )
        red_count = (await self.db.execute(red_stmt)).scalar() or 0

        yellow_stmt = (
            select(func.count())
            .select_from(ClauseAnalysis)
            .where(ClauseAnalysis.risk_level == "yellow")
        )
        yellow_count = (await self.db.execute(yellow_stmt)).scalar() or 0

        green_stmt = (
            select(func.count())
            .select_from(ClauseAnalysis)
            .where(ClauseAnalysis.risk_level == "green")
        )
        green_count = (await self.db.execute(green_stmt)).scalar() or 0

        return {
            # 原有字段
            "totalRules": total_rules,
            "avgConfidence": round(float(avg_confidence), 2),
            "totalLaws": total_laws,
            "pendingReview": pending,
            # 新增字段
            "totalContracts": total_contracts,
            "thisMonth": this_month,
            "avgScore": round(float(avg_score), 1),
            "redCount": red_count,
            "yellowCount": yellow_count,
            "greenCount": green_count,
        }

    async def get_pending(self) -> list[dict]:
        """获取待审核规则"""
        stmt = (
            select(KnowledgeRule)
            .where(KnowledgeRule.source == "auto_learned")
            .where(KnowledgeRule.confidence < 0.7)
            .order_by(KnowledgeRule.confidence.desc())
        )
        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        return [
            {
                "id": rule.id,
                "text": rule.rule_text,
                "source": rule.source,
                "confidence": rule.confidence,
            }
            for rule in rules
        ]

    async def get_laws(self) -> list[dict]:
        """获取法规列表"""
        stmt = select(LegalReference).order_by(LegalReference.law_name)
        result = await self.db.execute(stmt)
        refs = result.scalars().all()

        # 按法规名分组
        law_map: dict[str, dict] = {}
        for ref in refs:
            name = ref.law_name
            if name not in law_map:
                law_map[name] = {"name": name, "articles": 0, "tags": set()}
            law_map[name]["articles"] += 1
            if ref.tags:
                try:
                    tags = json.loads(ref.tags)
                    law_map[name]["tags"].update(tags)
                except (json.JSONDecodeError, TypeError):
                    pass

        return [
            {"name": v["name"], "articles": v["articles"], "tags": sorted(v["tags"])}
            for v in law_map.values()
        ]

    async def approve_rule(self, rule_id: str) -> None:
        """通过待审核规则"""
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == rule_id)
        result = await self.db.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule:
            rule.confidence = min(rule.confidence + 0.2, 1.0)
            rule.source = "manual"
            rule.updated_at = datetime.now(timezone.utc)
            logger.info("审核通过规则: id=%s", rule_id)

    async def reject_rule(self, rule_id: str) -> None:
        """拒绝待审核规则"""
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == rule_id)
        result = await self.db.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule:
            rule.is_active = False
            rule.updated_at = datetime.now(timezone.utc)
            logger.info("审核拒绝规则: id=%s", rule_id)
