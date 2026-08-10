"""Agent Pipeline — 三段式 Prompt Chaining + Parallelization"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Callable

from server.core import document_ingress
from server.core.knowledge import KnowledgeEngine
from server.core.llm import LLMGateway, get_llm_gateway
from server.core.ocr import OCREngine, get_ocr_engine
from server.core.workers.evaluator import EvaluationResult, evaluate
from server.core.workers.workers import (
    ClauseRisk,
    analyze_dimension,
    analyze_dimension_with_context,
    detect_conflicts,
)
from server.core.workers.parser import ClauseItem, ParseResult, parse_contract

# 向后兼容：旧代码可能从 agent 模块导入 TYPE_EN_MAP
from server.core.workers.parser import TYPE_EN_MAP  # noqa: F401

from server.models.database import async_session_factory

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果（保持与原有接口兼容）"""

    contract_id: str = ""
    contract_type: str = ""
    contract_type_en: str = "other"
    overall_score: int = 0
    recommendation: str = "negotiate_first"
    summary: str = ""
    model_used: str = ""
    clauses: list[dict] = field(default_factory=list)
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0
    needs_review: list[str] = field(default_factory=list)
    top_risks: list[str] = field(default_factory=list)
    ocr_text: str = ""  # 文档解析全文（AnyDoc/OCR；字段名保持兼容，供原文标注视图）
    error: str = ""  # 分析失败时的错误信息，调用方可据此判断成功/失败


# Worker 维度列表
DIMENSIONS = ["equity", "financial", "ip", "dispute", "general"]


class ContractAgent:
    """合同分析 Agent — 三段式 Pipeline"""

    def __init__(
        self,
        llm: LLMGateway | None = None,
        ocr: OCREngine | None = None,
    ) -> None:
        self.llm = llm or get_llm_gateway()
        # 保留 ocr 参数以兼容旧调用方；解析统一走 document_ingress
        self.ocr = ocr or get_ocr_engine()

    async def analyze(
        self,
        file_path: str,
        contract_type_hint: str | None = None,
        on_step: Callable | None = None,
    ) -> AnalysisResult:
        """完整的三段式分析流程"""

        async def _notify(step: int, total: int, message: str) -> None:
            if on_step:
                try:
                    await on_step(step, total, message)
                except Exception:
                    pass

        result = AnalysisResult()
        contract_id = uuid.uuid4().hex

        # ── 文档解析（AnyDoc / PaddleOCR / 纯文本）──
        await _notify(1, 5, "正在识别文字...")
        logger.info("文档解析开始")
        try:
            doc_result = await self._retry(
                lambda: document_ingress.ingest(file_path), "文档解析"
            )
            if not doc_result or not doc_result.full_text.strip():
                logger.error("文档解析结果为空")
                result.error = "文档解析结果为空，无法分析"
                return result
            full_text = doc_result.full_text
            result.ocr_text = full_text  # 字段名保持 ocr_text，内容可为 Markdown

            if doc_result.confidence_avg < 0.7:
                logger.warning(
                    "文档解析置信度较低: %.2f (source=%s)",
                    doc_result.confidence_avg,
                    doc_result.source,
                )
        except Exception as e:
            logger.error("文档解析失败: %s", e)
            result.error = f"文档解析失败: {e}"
            return result

        # ── Stage 1: 结构解析 ──
        await _notify(2, 5, "正在解析合同结构...")
        logger.info("Stage 1: 结构解析")
        try:
            parse_result = await parse_contract(full_text, self.llm, contract_type_hint)
        except Exception as e:
            logger.error("Stage 1 失败: %s", e)
            # 兜底：全文作为一个条款
            parse_result = ParseResult(
                contract_type=contract_type_hint or "其他",
                clauses=[ClauseItem(
                    id="1", type="other", title="全文",
                    text=full_text[:2000], relevance=["general"],
                )],
            )

        result.contract_type = parse_result.contract_type
        result.contract_type_en = parse_result.contract_type_en
        result.model_used = parse_result.recommended_model

        # ── 知识库检索（超时降级） ──
        kb_rules: list[str] = []
        kb_laws: list[dict] = []

        # 设置 embedding 下载进度回调（首次下载时显示进度）
        from server.core import embedding

        def _embedding_progress(current: int, total: int, desc: str):
            """embedding 模型下载进度回调（在线程池中调用）"""
            if total > 0:
                # 计算下载大小（模型约 400MB）
                mb_current = current / 1024 / 1024 if current > 10000 else current
                mb_total = total / 1024 / 1024 if total > 10000 else total
                msg = f"下载知识库模型: {mb_current:.1f}/{mb_total:.1f}MB"
            else:
                msg = f"下载知识库模型: {desc or '准备中...'}"

            # 通过 asyncio 打包同步回调为异步任务
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(_notify(2, 5, msg))
            except Exception:
                pass

        embedding.set_progress_callback(_embedding_progress)

        try:
            async with async_session_factory() as db:
                knowledge = KnowledgeEngine(db)
                # 使用 wait_for 设置超时，避免 embedding 模型下载卡住
                kb_rules = await asyncio.wait_for(
                    knowledge.search(full_text[:500], parse_result.contract_type),
                    timeout=60.0,  # 60 秒超时（给模型下载更多时间）
                )
                kb_laws = await asyncio.wait_for(
                    knowledge.search_laws(full_text[:500], parse_result.contract_type),
                    timeout=10.0,
                )
        except asyncio.TimeoutError:
            logger.warning("知识库检索超时（60s），跳过知识库增强，继续分析")
        except Exception as e:
            logger.warning("知识库检索失败: %s，跳过知识库增强", e)
        finally:
            # 确保回调被清除
            embedding._clear_progress_callback()

        # ── Stage 2: 并行风险评估（含冲突解决） ──
        total_workers = len(DIMENSIONS)
        await _notify(3, 5, f"正在并行分析 {total_workers} 个维度...")
        logger.info("Stage 2: 并行风险评估 (%d 个 Worker)", total_workers)

        worker_tasks = [
            analyze_dimension(dim, parse_result.clauses, self.llm, parse_result.contract_type, kb_rules, kb_laws)
            for dim in DIMENSIONS
        ]
        worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        # 合并所有 Worker 结果
        all_risks: list[ClauseRisk] = []
        for dim, res in zip(DIMENSIONS, worker_results):
            if isinstance(res, Exception):
                logger.warning("Worker[%s] 失败: %s", dim, res)
            elif isinstance(res, list):
                all_risks.extend(res)

        # ── 冲突检测 + 第二轮带上下文分析 ──
        conflicts = detect_conflicts(all_risks)
        if conflicts:
            logger.info("发现 %d 个冲突条款，启动第二轮分析", len(conflicts))
            await _notify(3, 5, f"发现 {len(conflicts)} 个维度冲突，正在协调...")

            # 构建条款 id → ClauseItem 的映射
            clause_map = {c.id: c for c in parse_result.clauses}

            for clause_id, conflict_risks in conflicts.items():
                clause = clause_map.get(clause_id)
                if not clause:
                    continue

                # 构建跨维度上下文摘要
                cross_context = "\n".join(
                    f"- {r.risk_type or '未知维度'}: {r.risk_level} — {r.issue}"
                    for r in conflict_risks
                )

                # 找到评级最高的维度（red > yellow > green）来重新分析
                risk_priority = {"red": 3, "yellow": 2, "green": 1}
                best_risk = max(conflict_risks, key=lambda r: risk_priority.get(r.risk_level, 0))
                # 从 best_risk 的 risk_type 推断维度
                resolve_dim = "equity"  # 默认用权责对等维度做最终裁决

                new_risk = await analyze_dimension_with_context(
                    resolve_dim, clause, self.llm, parse_result.contract_type,
                    cross_context, kb_rules, kb_laws,
                )

                if new_risk:
                    # 用新结果替换冲突中的旧结果
                    all_risks = [
                        r for r in all_risks
                        if not (r.clause_id == clause_id and r.risk_type == best_risk.risk_type)
                    ]
                    all_risks.append(new_risk)
                    logger.info(
                        "条款 %s 冲突解决: %s → %s",
                        clause_id, best_risk.risk_level, new_risk.risk_level,
                    )

        # ── Stage 3: 聚合评分 ──
        await _notify(4, 5, "正在聚合评分...")
        logger.info("Stage 3: 聚合评分")
        try:
            eval_result = await evaluate(all_risks, self.llm)
        except Exception as e:
            logger.warning("Stage 3 失败: %s", e)
            # 兜底：直接统计
            eval_result = EvaluationResult()
            for r in all_risks:
                if r.risk_level in eval_result.risk_distribution:
                    eval_result.risk_distribution[r.risk_level] += 1

        # ── 组装最终结果 ──
        await _notify(5, 5, "正在生成报告...")
        result.overall_score = eval_result.overall_score
        result.recommendation = eval_result.recommendation
        result.summary = eval_result.one_line_summary
        result.needs_review = eval_result.needs_review
        result.top_risks = eval_result.top_risks
        result.red_count = eval_result.risk_distribution.get("red", 0)
        result.yellow_count = eval_result.risk_distribution.get("yellow", 0)
        result.green_count = eval_result.risk_distribution.get("green", 0)

        # 组装条款列表（合并解析结果和风险评估结果）
        # 同一 clause_id + 同一维度只保留 severity 最高的
        risk_map: dict[str, ClauseRisk] = {}
        for r in all_risks:
            key = r.clause_id
            if key not in risk_map or r.severity > risk_map[key].severity:
                risk_map[key] = r

        for clause in parse_result.clauses:
            risk = risk_map.get(clause.id)
            clause_dict = {
                "clause_number": clause.id,
                "title": clause.title,
                "content": clause.text,
                "type": clause.type,
                "risk_level": risk.risk_level if risk else "green",
                "risk_type": risk.risk_type if risk else "未分析",
                "risk_summary": risk.issue if risk else "本维度无明显风险",
                "plain_explanation": risk.issue if risk else "",
                "severity_score": risk.severity if risk else 1,
                "suggested_clause": risk.suggestion if risk else "",
                "legal_basis": risk.legal_basis if risk else "",
                "unfavorable_to": risk.unfavorable_to if risk else "",
                "needs_review": clause.id in eval_result.needs_review,
            }
            result.clauses.append(clause_dict)

        result.contract_id = contract_id
        logger.info(
            "分析完成: score=%d red=%d yellow=%d green=%d review=%d",
            result.overall_score,
            result.red_count,
            result.yellow_count,
            result.green_count,
            len(result.needs_review),
        )
        return result

    async def _retry(self, fn, step_name: str, max_retries: int = 2):
        """带重试的异步调用"""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await fn()
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning("%s 重试 %d/%d: %s", step_name, attempt + 1, max_retries, e)
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise last_error  # type: ignore
