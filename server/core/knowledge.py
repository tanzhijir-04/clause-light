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


def effective_rule_status(rule: KnowledgeRule) -> str:
    """解析规则生效状态：优先 status，兼容仅设 is_active 的旧数据"""
    status = rule.status
    if not status:
        return "active" if rule.is_active else "disabled"
    # pending / disabled / rolled_back 以 status 为准（即使 is_active 仍为 True）
    if status != "active":
        return status
    # status=active 但 is_active=False：视为禁用（Column 默认 status=active 的兼容）
    if not rule.is_active:
        return "disabled"
    return "active"


def sync_rule_is_active(rule: KnowledgeRule) -> None:
    """根据 status 同步兼容字段 is_active（以 status 字段为准）"""
    status = rule.status or ("active" if rule.is_active else "disabled")
    if not rule.status:
        rule.status = status
    rule.is_active = status == "active"


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
        混合检索相关规则（关键词 + 语义向量）。

        1. 仅返回 status==active 的规则（兼容缺失 status 时回退 is_active）
        2. 按 category 过滤（通用 + 对应合同类型）
        3. 关键词匹配评分
        4. 如果 embedding 可用，叠加语义相似度评分
        5. 按综合得分降序排序，返回 Top K
        """
        from server.core import embedding

        category = TYPE_CATEGORY_MAP.get(contract_type, "其他")

        stmt = select(KnowledgeRule)
        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        # 过滤出 active 且匹配类别的规则
        filtered = [
            r for r in rules
            if effective_rule_status(r) == "active"
            and (r.category == "通用" or r.category == category)
        ]

        if not filtered:
            return []

        # ── 关键词评分 ──
        query_lower = query.lower()
        keyword_scores: dict[str, float] = {}

        for rule in filtered:
            score = 0.0
            rule_lower = rule.rule_text.lower()
            if query_lower in rule_lower:
                score += 2.0

            if rule.trigger_keywords:
                try:
                    keywords = json.loads(rule.trigger_keywords)
                    for kw in keywords:
                        if kw.lower() in query_lower:
                            score += 1.0
                except (json.JSONDecodeError, TypeError):
                    pass

            keyword_scores[rule.id] = score

        # ── 语义向量评分（如果可用） ──
        vector_scores: dict[str, float] = {}
        if await embedding.is_available_async():
            try:
                # 编码查询文本（使用同步版本，因为模型已加载）
                query_vec = embedding.encode_single(query)
                if query_vec is not None:
                    import numpy as np

                    # 收集有 embedding 的规则
                    rules_with_vec = []
                    vecs = []
                    for rule in filtered:
                        if rule.embedding:
                            try:
                                vec = json.loads(rule.embedding)
                                if isinstance(vec, list) and len(vec) > 0:
                                    rules_with_vec.append(rule)
                                    vecs.append(vec)
                            except (json.JSONDecodeError, TypeError):
                                pass

                    if vecs:
                        corpus_vecs = np.array(vecs, dtype=np.float32)
                        query_np = np.array(query_vec, dtype=np.float32)
                        similarities = embedding.batch_similarity(query_np, corpus_vecs)

                        for rule, sim in zip(rules_with_vec, similarities):
                            vector_scores[rule.id] = float(sim) * 3.0  # 放大向量得分权重
            except Exception as e:
                logger.warning("向量检索失败，降级为纯关键词搜索: %s", e)

        # ── 混合评分 ──
        # α=0.6 关键词 + 0.4 向量（如果向量可用），否则纯关键词
        has_vectors = bool(vector_scores)
        alpha = 0.6 if has_vectors else 1.0

        matched: list[tuple[KnowledgeRule, float]] = []
        for rule in filtered:
            kw = keyword_scores.get(rule.id, 0.0)
            vec = vector_scores.get(rule.id, 0.0)
            final_score = alpha * kw + (1 - alpha) * vec + rule.confidence * 0.1
            if final_score > 0.1:  # 阈值过滤
                matched.append((rule, final_score))

        matched.sort(key=lambda x: x[1], reverse=True)

        # 更新使用次数
        for rule, _ in matched[:top_k]:
            rule.usage_count = (rule.usage_count or 0) + 1

        logger.info(
            "知识库检索: query='%s' 匹配 %d/%d 条 (向量=%s)",
            query[:20], len(matched), len(filtered), has_vectors,
        )
        return [rule.rule_text for rule, _ in matched[:top_k]]

    async def add_rule(self, rule_data: dict) -> dict:
        """新增规则"""
        status = rule_data.get("status", "active")
        rule = KnowledgeRule(
            id=uuid.uuid4().hex,
            category=rule_data.get("category", "通用"),
            rule_text=rule_data["rule_text"],
            trigger_keywords=json.dumps(rule_data.get("trigger_keywords", []), ensure_ascii=False),
            confidence=rule_data.get("confidence", 0.5),
            source=rule_data.get("source", "manual"),
            status=status,
            is_active=status == "active",
        )
        sync_rule_is_active(rule)
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
        if "status" in data:
            rule.status = data["status"]
            sync_rule_is_active(rule)
        elif "is_active" in data:
            rule.is_active = data["is_active"]
            rule.status = "active" if data["is_active"] else "disabled"
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
        """获取待审核规则（status=pending）"""
        stmt = (
            select(KnowledgeRule)
            .where(KnowledgeRule.status == "pending")
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
                "status": rule.status or "pending",
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
        """通过待审核规则 → status=active 并同步 is_active"""
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == rule_id)
        result = await self.db.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule:
            rule.confidence = min(rule.confidence + 0.2, 1.0)
            rule.source = "manual"
            rule.status = "active"
            sync_rule_is_active(rule)
            rule.updated_at = datetime.now(timezone.utc)
            logger.info("审核通过规则: id=%s", rule_id)

    async def reject_rule(self, rule_id: str) -> None:
        """拒绝待审核规则"""
        stmt = select(KnowledgeRule).where(KnowledgeRule.id == rule_id)
        result = await self.db.execute(stmt)
        rule = result.scalar_one_or_none()
        if rule:
            rule.status = "disabled"
            sync_rule_is_active(rule)
            rule.updated_at = datetime.now(timezone.utc)
            logger.info("审核拒绝规则: id=%s", rule_id)

    async def search_laws(
        self,
        clause_text: str,
        contract_type: str = "",
        top_k: int = 3,
    ) -> list[dict]:
        """
        检索与条款内容相关的法律条文。

        匹配策略：
        1. 按标签匹配（优先）
        2. 按内容关键词匹配
        返回 top_k 条最相关的法条。
        """
        stmt = select(LegalReference)
        result = await self.db.execute(stmt)
        refs = result.scalars().all()

        if not refs:
            return []

        scored: list[tuple[LegalReference, float]] = []
        text_lower = clause_text.lower()

        for ref in refs:
            score = 0.0

            # 标签匹配
            if ref.tags:
                try:
                    tags = json.loads(ref.tags)
                    for tag in tags:
                        if tag.lower() in text_lower:
                            score += 3.0
                except (json.JSONDecodeError, TypeError):
                    pass

            # 内容关键词匹配（法条名称 + 条文内容中的关键词）
            if ref.content and ref.content.lower() in text_lower:
                score += 2.0
            if ref.article_number and ref.article_number in clause_text:
                score += 1.0

            # 合同类型相关的法律优先（如劳动合同用劳动合同法）
            if contract_type:
                type_law_map = {
                    "劳动合同": "劳动合同法",
                    "租赁合同": "民法典",
                    "装修合同": "民法典",
                    "借款合同": "民法典",
                }
                expected_law = type_law_map.get(contract_type, "")
                if expected_law and expected_law in (ref.law_name or ""):
                    score += 1.0

            if score > 0:
                scored.append((ref, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                "id": ref.id,
                "law_name": ref.law_name,
                "article_number": ref.article_number,
                "content": ref.content,
                "effective_date": ref.effective_date.isoformat() if ref.effective_date else None,
                "source_url": ref.source_url,
                "verified_at": ref.verified_at.isoformat() if ref.verified_at else None,
            }
            for ref, _ in scored[:top_k]
        ]

    async def trigger_auto_learning(self, clause: ClauseAnalysis) -> dict | None:
        """
        从用户"不正确"反馈中自动学习，创建新的待审核规则。

        流程：
        1. 检查是否已存在相似规则（避免重复）
        2. 从条款内容中提取关键词
        3. 创建新的知识规则（source=auto_learned, confidence=0.6）
        4. 规则进入待审核队列，等待管理员确认
        """
        clause_content = (clause.clause_content or "").strip()
        if not clause_content:
            logger.info("自动学习跳过：条款内容为空")
            return None

        # 检查是否已存在包含相同内容的规则（避免重复学习）
        existing_stmt = select(KnowledgeRule).where(
            KnowledgeRule.rule_text == clause_content
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            logger.info("自动学习跳过：规则已存在 clause_id=%s", clause.id)
            return None

        # 提取关键词（取条款内容的前 20 个字作为触发词）
        keywords = _extract_keywords(clause_content)

        # 通过 Analysis -> Contract 获取合同类型，映射到规则类别
        category = "通用"
        if clause.analysis_id:
            analysis_stmt = select(Analysis).where(Analysis.id == clause.analysis_id)
            analysis_result = await self.db.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none()
            if analysis and analysis.contract_id:
                contract_stmt = select(Contract).where(Contract.id == analysis.contract_id)
                contract_result = await self.db.execute(contract_stmt)
                contract = contract_result.scalar_one_or_none()
                if contract and contract.type:
                    category = TYPE_CATEGORY_MAP.get(contract.type, "通用")

        new_rule = {
            "category": category,
            "rule_text": clause_content,
            "trigger_keywords": keywords,
            "confidence": 0.6,
            "source": "auto_learned",
        }

        result = await self.add_rule(new_rule)
        logger.info(
            "自动学习：从反馈创建新规则 clause_id=%s rule_id=%s",
            clause.id,
            result["id"],
        )
        return result


def _extract_keywords(text: str, max_keywords: int = 5) -> list[str]:
    """
    从条款文本中提取关键词。

    简单策略：按标点分割，取较短的有意义片段作为关键词。
    后续可替换为更复杂的 NLP 分词。
    """
    # 按常见中文标点分割
    import re
    parts = re.split(r"[，。；：、！？\s]+", text)
    # 过滤空串和过长片段，取前 max_keywords 个
    keywords = [p.strip() for p in parts if 2 < len(p.strip()) <= 20]
    return keywords[:max_keywords]
