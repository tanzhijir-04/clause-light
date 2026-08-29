"""Agent Pipeline — 三段式 Prompt Chaining + Parallelization"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable

from server.core import document_ingress
from server.core.knowledge import KnowledgeEngine
from server.core.llm import LLMGateway, get_llm_gateway
from server.core.ocr import OCREngine, get_ocr_engine
from server.core.workers.evaluator import (
    EvaluationResult,
    evaluate,
    select_final_risks,
)
from server.core.workers.workers import (
    ClauseRisk,
    analyze_dimension,
    analyze_dimension_with_context,
    detect_conflicts,
    failed_clause_risk,
    requires_resolution,
)
from server.core.workers.parser import (
    TYPE_TO_WORKERS,
    ClauseItem,
    ParseResult,
    _utf16_length,
    parse_contract,
    normalize_contract_text,
)

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
    overall_score: int | None = None
    recommendation: str = "manual_review"
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
    session_id: str = ""  # L0 记忆会话 id（可选，旧客户端可忽略）
    analysis_status: str = "failed"
    review_reasons: dict[str, list[str]] = field(default_factory=dict)
    worker_risks: list[dict] = field(default_factory=list)
    processing_mode: str = ""


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

        def _pipeline_failure(message: str) -> AnalysisResult:
            result.error = message
            result.recommendation = "manual_review"
            result.summary = "系统未形成可用分析，请人工复核"
            result.analysis_status = "failed"
            result.review_reasons = {"pipeline": [message]}
            return result

        # ── 文档解析（AnyDoc / PaddleOCR / 纯文本）──
        await _notify(1, 5, "正在识别文字...")
        logger.info("文档解析开始")
        try:
            doc_result = await self._retry(
                lambda: document_ingress.ingest(file_path), "文档解析"
            )
            if not doc_result or not doc_result.full_text.strip():
                logger.error("文档解析结果为空")
                return _pipeline_failure("文档解析结果为空，无法分析")
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
            return _pipeline_failure(f"文档解析失败: {e}")

        # ── Stage 1: 结构解析 ──
        await _notify(2, 5, "正在解析合同结构...")
        logger.info("Stage 1: 结构解析")
        parse_failed = False
        parse_failure_reason = ""
        try:
            parse_result = await parse_contract(full_text, self.llm, contract_type_hint)
        except Exception as e:
            logger.error("Stage 1 失败: %s", e)
            parse_failed = True
            parse_failure_reason = str(e)
            # 兜底：全文作为一个条款
            parse_result = ParseResult(
                contract_type=contract_type_hint or "其他",
                clauses=[ClauseItem(
                    id="1", type="other", title="全文",
                    text=normalize_contract_text(full_text), relevance=["general"],
                    source_start=0,
                    source_end=_utf16_length(normalize_contract_text(full_text)),
                    review_required=True,
                    review_reason=str(e),
                )],
                parse_failed=True,
                failure_reason=str(e),
                parse_status="fallback",
                review_required=True,
                fallback_reason=str(e),
            )

        parse_failed = parse_failed or parse_result.parse_failed
        parse_failure_reason = (
            parse_failure_reason
            or parse_result.fallback_reason
            or parse_result.failure_reason
        )
        if parse_failed:
            result.error = f"合同结构解析失败: {parse_failure_reason or '未知原因'}"

        result.contract_type = parse_result.contract_type
        result.contract_type_en = parse_result.contract_type_en
        result.model_used = parse_result.recommended_model

        # ── 知识库检索（超时降级） ──
        kb_rules: list[str] = []
        kb_laws: list[dict] = []
        laws_by_clause: dict[str, list[dict]] = {}

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
                # 法条检索按条款串行执行：同一个 AsyncSession 不并发使用。
                for clause in parse_result.clauses:
                    try:
                        laws = await asyncio.wait_for(
                            knowledge.search_laws(
                                clause.text,
                                parse_result.contract_type,
                                top_k=3,
                            ),
                            timeout=10.0,
                        )
                    except Exception as exc:
                        logger.warning("条款法条检索失败 clause=%s: %s", clause.id, exc)
                        laws = []
                    laws_by_clause[clause.id] = laws
                    clause.law_references = laws
                    for law in laws:
                        if law.get("id") not in {item.get("id") for item in kb_laws}:
                            kb_laws.append(law)
        except asyncio.TimeoutError:
            logger.warning("知识库检索超时（60s），跳过知识库增强，继续分析")
        except Exception as e:
            logger.warning("知识库检索失败: %s，跳过知识库增强", e)
        finally:
            # 确保回调被清除
            embedding._clear_progress_callback()

        # ── 记忆会话 + Loadout / Stage 上下文（失败降级为空）──
        memory_context = ""
        try:
            from server.core.agent_tools import build_loadout, build_stage_context
            from server.core.memory.kernel import MemoryKernel

            async with async_session_factory() as db:
                kernel = MemoryKernel(db)
                session_id = await kernel.start_session(
                    contract_id, parse_result.contract_type
                )
                result.session_id = session_id
                await kernel.append_event(
                    session_id,
                    "step",
                    {
                        "name": "parse_done",
                        "clauses": len(parse_result.clauses),
                        "contract_type": parse_result.contract_type,
                    },
                )
                query_text = full_text[:500]
                loadout = await build_loadout(
                    db,
                    contract_type=parse_result.contract_type,
                    query=query_text,
                )
                stage = await build_stage_context(
                    db,
                    contract_type=parse_result.contract_type,
                    query=query_text,
                    kb_rules=kb_rules,
                )
                parts = [p for p in (loadout, stage) if p and p.strip()]
                memory_context = "\n\n".join(parts)
                await kernel.append_event(
                    session_id,
                    "step",
                    {
                        "name": "memory_loadout",
                        "chars": len(memory_context),
                    },
                )
                await db.commit()
        except Exception as e:
            logger.warning("记忆装配失败，降级为空上下文: %s", e)

        # ── Stage 2: 并行风险评估（含冲突解决） ──
        # Parser normally sanitizes this field; repeat the guard at the dispatch
        # boundary so malformed or externally constructed ParseResults cannot
        # route a Worker using an unknown dimension.
        for clause in parse_result.clauses:
            relevance = clause.relevance
            if (
                not isinstance(relevance, list)
                or not relevance
                or any(dimension not in DIMENSIONS for dimension in relevance)
            ):
                clause_type = clause.type if clause.type in TYPE_TO_WORKERS else "other"
                clause.relevance = TYPE_TO_WORKERS[clause_type].copy()
                clause.review_required = True
                clause.review_reason = (
                    clause.review_reason or "relevance 无效，已按条款类型映射"
                )
                parse_result.review_required = True

        total_workers = len(DIMENSIONS)
        await _notify(3, 5, f"正在并行分析 {total_workers} 个维度...")
        logger.info("Stage 2: 并行风险评估 (%d 个 Worker)", total_workers)

        worker_tasks = [
            analyze_dimension(
                dim,
                parse_result.clauses,
                self.llm,
                parse_result.contract_type,
                kb_rules,
                kb_laws,
                memory_context=memory_context,
            )
            for dim in DIMENSIONS
        ]
        worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        # 合并所有 Worker 结果，同时丢弃不属于本维度请求的条款 id。
        all_risks: list[ClauseRisk] = []
        for dim, res in zip(DIMENSIONS, worker_results):
            relevant_clauses = [
                clause for clause in parse_result.clauses if dim in clause.relevance
            ]
            expected_ids = {clause.id for clause in relevant_clauses}
            if isinstance(res, Exception):
                logger.warning("Worker[%s] 失败: %s", dim, res)
                all_risks.extend(
                    failed_clause_risk(clause, dim, str(res))
                    for clause in relevant_clauses
                )
            elif isinstance(res, list):
                accepted = [risk for risk in res if risk.clause_id in expected_ids]
                foreign = [risk for risk in res if risk.clause_id not in expected_ids]
                if foreign:
                    logger.warning(
                        "Worker[%s] 返回非请求条款 id=%s，已忽略",
                        dim,
                        sorted({risk.clause_id for risk in foreign}),
                    )
                all_risks.extend(accepted)
                returned_ids = {risk.clause_id for risk in accepted}
                all_risks.extend(
                    failed_clause_risk(clause, dim, "Worker 未返回该条款评级")
                    for clause in relevant_clauses
                    if clause.id not in returned_ids
                )

        # Worker 返回空列表时也要为相关条款留下可复核的失败结果。
        for clause in parse_result.clauses:
            if not any(r.clause_id == clause.id for r in all_risks):
                dimension = clause.relevance[0] if clause.relevance else "general"
                all_risks.append(
                    failed_clause_risk(clause, dimension, "未获得 Worker 分析结果")
                )

        # ── 冲突检测 + 第二轮带上下文分析 ──
        initial_risks = list(all_risks)
        resolution_risks: list[ClauseRisk] = []
        conflicts = detect_conflicts(initial_risks)
        if conflicts:
            logger.info("发现 %d 个冲突条款，启动第二轮分析", len(conflicts))
            await _notify(3, 5, f"发现 {len(conflicts)} 个维度冲突，正在协调...")

            # 构建条款 id → ClauseItem 的映射
            clause_map = {c.id: c for c in parse_result.clauses}
            # 冲突工具预算：每个分析请求最多额外增强 2 个冲突条款簇
            conflict_tool_budget = 2

            for clause_id, conflict_risks in conflicts.items():
                conflict_reason = (
                    "同一条款存在多个有效维度评级差异: "
                    + ", ".join(
                        f"{risk.dimension}={risk.risk_level}" for risk in conflict_risks
                    )
                )
                for risk in conflict_risks:
                    risk.review_required = True
                    if conflict_reason not in risk.review_reason:
                        risk.review_reason = (
                            f"{risk.review_reason}; {conflict_reason}"
                            if risk.review_reason
                            else conflict_reason
                        )

                if not requires_resolution(conflict_risks):
                    continue

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
                best_risk = max(
                    conflict_risks,
                    key=lambda r: (risk_priority.get(r.risk_level, 0), r.severity),
                )
                resolve_dim = best_risk.dimension
                if resolve_dim not in DIMENSIONS:
                    logger.warning(
                        "条款 %s 冲突维度无效: %s，跳过冲突复核",
                        clause_id,
                        resolve_dim,
                    )
                    continue

                # 按需调用 memory/wiki/skill 工具（预算内）
                conflict_memory = memory_context
                if conflict_tool_budget > 0:
                    try:
                        from server.core.agent_tools import run_conflict_tools

                        async with async_session_factory() as db:
                            bundle = await run_conflict_tools(
                                db,
                                query=clause.text or clause.title,
                                contract_type=parse_result.contract_type,
                            )
                            extra = "\n".join(
                                x
                                for x in (
                                    bundle.memory_text,
                                    bundle.wiki_text,
                                    bundle.skill_text,
                                )
                                if x and x.strip()
                            )
                            if extra:
                                conflict_memory = (
                                    f"{memory_context}\n{extra}".strip()
                                    if memory_context
                                    else extra
                                )
                            conflict_tool_budget -= 1
                            if result.session_id:
                                try:
                                    from server.core.memory.kernel import MemoryKernel

                                    kernel = MemoryKernel(db)
                                    await kernel.append_event(
                                        result.session_id,
                                        "tool",
                                        {
                                            "name": "conflict_tools",
                                            "clause_id": clause_id,
                                            "chars": len(extra),
                                        },
                                    )
                                    await db.commit()
                                except Exception:
                                    pass
                    except Exception as e:
                        logger.warning("冲突工具调用失败，仅用原上下文: %s", e)
                        conflict_tool_budget -= 1

                try:
                    new_risk = await analyze_dimension_with_context(
                        resolve_dim,
                        clause,
                        self.llm,
                        parse_result.contract_type,
                        cross_context,
                        kb_rules,
                        clause.law_references or [],
                        memory_context=conflict_memory,
                    )
                except Exception as exc:
                    new_risk = failed_clause_risk(clause, resolve_dim, str(exc))

                if new_risk and new_risk.clause_id != clause_id:
                    logger.warning(
                        "冲突解决返回非请求条款 id=%s，期望=%s",
                        new_risk.clause_id,
                        clause_id,
                    )
                    new_risk = failed_clause_risk(
                        clause,
                        resolve_dim,
                        f"冲突解决返回了非请求条款 id={new_risk.clause_id}",
                    )
                    new_risk.phase = "resolution"

                if new_risk:
                    new_risk.phase = "resolution"
                    if (
                        new_risk.analysis_status == "completed"
                        and new_risk.risk_level in {"red", "yellow", "green"}
                    ):
                        new_risk.analysis_status = "resolved"
                    new_risk.review_required = True
                    new_risk.review_reason = (
                        f"{new_risk.review_reason}; {conflict_reason}"
                        if new_risk.review_reason
                        else conflict_reason
                    )
                    resolution_risks.append(new_risk)
                    logger.info(
                        "条款 %s 冲突解决: %s → %s",
                        clause_id, best_risk.risk_level, new_risk.risk_level,
                    )

        all_risks = initial_risks + resolution_risks

        # ── Stage 3: 聚合评分 ──
        await _notify(4, 5, "正在聚合评分...")
        logger.info("Stage 3: 聚合评分")
        evaluation_failed = False
        try:
            eval_result = await evaluate(select_final_risks(all_risks), self.llm)
        except Exception as e:
            logger.warning("Stage 3 失败: %s", e)
            evaluation_failed = True
            # 兜底：直接统计
            eval_result = EvaluationResult(
                overall_score=None,
                recommendation="manual_review",
                one_line_summary="系统未形成可用评级，请人工复核",
            )
            for r in all_risks:
                if r.risk_level in eval_result.risk_distribution:
                    eval_result.risk_distribution[r.risk_level] += 1
                if r.review_required or r.risk_level == "unknown":
                    if r.clause_id not in eval_result.needs_review:
                        eval_result.needs_review.append(r.clause_id)
            if not any(
                r.analysis_status in {"completed", "resolved"}
                and r.risk_level in {"red", "yellow", "green"}
                for r in all_risks
            ):
                eval_result.recommendation = "manual_review"
                eval_result.one_line_summary = "系统未形成可用评级，请人工复核"
                eval_result.overall_score = None
            eval_result.needs_review.sort()

        # ── 组装最终结果 ──
        await _notify(5, 5, "正在生成报告...")
        result.overall_score = eval_result.overall_score
        result.recommendation = eval_result.recommendation
        result.summary = eval_result.one_line_summary
        result.needs_review = sorted(
            set(eval_result.needs_review)
            | {r.clause_id for r in all_risks if r.review_required}
        )
        result.top_risks = eval_result.top_risks
        result.red_count = eval_result.risk_distribution.get("red", 0)
        result.yellow_count = eval_result.risk_distribution.get("yellow", 0)
        result.green_count = eval_result.risk_distribution.get("green", 0)
        result.processing_mode = "parallel"
        result.worker_risks = [asdict(r) for r in all_risks]
        result.review_reasons = {}
        if parse_failed:
            result.review_reasons["pipeline"] = [
                parse_failure_reason or "合同结构解析失败"
            ]
        elif parse_result.review_required:
            result.review_reasons["pipeline"] = [
                parse_result.fallback_reason
                or parse_result.failure_reason
                or "合同结构解析需要人工复核"
            ]
        for clause in parse_result.clauses:
            if clause.review_required:
                result.needs_review.append(clause.id)
                result.review_reasons.setdefault(clause.id, []).append(
                    clause.review_reason or "需要人工复核"
                )
        result.needs_review = sorted(set(result.needs_review))
        for risk in all_risks:
            if risk.review_required or risk.clause_id in result.needs_review:
                reason = risk.review_reason or risk.failure_reason or "需要人工复核"
                result.review_reasons.setdefault(risk.clause_id, []).append(reason)
        usable_risks = [
            risk
            for risk in all_risks
            if risk.analysis_status in {"completed", "resolved"}
            and risk.risk_level in {"red", "yellow", "green"}
        ]
        has_risk_failure = any(
            risk not in usable_risks or risk.review_required for risk in all_risks
        ) or parse_result.review_required or any(
            clause.review_required for clause in parse_result.clauses
        )
        evaluation_failed = evaluation_failed or (
            bool(usable_risks)
            and eval_result.overall_score is None
            and eval_result.recommendation == "manual_review"
        )
        if not usable_risks:
            result.analysis_status = "failed"
            if type(result.overall_score) is not int:
                result.overall_score = None
            result.recommendation = "manual_review"
            result.summary = "系统未形成可用评级，请人工复核"
        elif parse_failed or evaluation_failed or has_risk_failure:
            result.analysis_status = "partial"
        else:
            result.analysis_status = "completed"

        # 组装条款列表：展示结果可选用 resolution，但 Worker 历史不被覆盖。
        risk_map = {risk.clause_id: risk for risk in select_final_risks(all_risks)}

        for clause in parse_result.clauses:
            risk = risk_map.get(clause.id)
            if risk is None:
                dimension = clause.relevance[0] if clause.relevance else "general"
                risk = failed_clause_risk(clause, dimension, "未获得可用风险评级")
            clause_dict = {
                "clause_number": clause.id,
                "title": clause.title,
                "content": clause.text,
                "type": clause.type,
                "risk_level": risk.risk_level,
                "risk_type": risk.risk_type or "未分析",
                "risk_summary": risk.issue,
                "plain_explanation": risk.issue,
                "severity_score": risk.severity,
                "suggested_clause": risk.suggestion,
                "legal_basis": risk.legal_basis,
                "unfavorable_to": risk.unfavorable_to,
                "citation_ids": risk.citation_ids,
                "analysis_status": risk.analysis_status,
                "needs_review": (
                    clause.id in result.needs_review
                    or clause.review_required
                    or risk.review_required
                ),
                "source_start": clause.source_start,
                "source_end": clause.source_end,
            }
            result.clauses.append(clause_dict)

        result.contract_id = contract_id
        logger.info(
            "分析完成: score=%s red=%d yellow=%d green=%d review=%d",
            result.overall_score,
            result.red_count,
            result.yellow_count,
            result.green_count,
            len(result.needs_review),
        )

        # ── 结束后 Distill（await + 吞异常，不阻断主结果）──
        await self._trigger_distill(result)

        return result

    async def _trigger_distill(self, result: AnalysisResult) -> None:
        """分析成功后触发 Distill；失败只记日志。"""
        if not result.session_id or result.error:
            return
        try:
            from server.core.distill.pipeline import distill_from_analysis
            from server.core.memory.kernel import MemoryKernel

            clause_summaries = [
                {
                    "clause_id": c.get("clause_number"),
                    "title": c.get("title"),
                    "risk_level": c.get("risk_level"),
                    "risk_summary": c.get("risk_summary"),
                }
                for c in result.clauses
            ]
            async with async_session_factory() as db:
                await asyncio.wait_for(
                    distill_from_analysis(
                        db,
                        self.llm,
                        session_id=result.session_id,
                        contract_type=result.contract_type or "",
                        clause_summaries=clause_summaries,
                    ),
                    timeout=30.0,
                )
                try:
                    kernel = MemoryKernel(db)
                    await kernel.append_event(
                        result.session_id,
                        "distill_done",
                        {"ok": True},
                    )
                except Exception as ev_err:
                    logger.warning("写入 distill_done 事件失败: %s", ev_err)
                await db.commit()
        except Exception as e:
            logger.warning("Distill 触发失败（不影响分析结果）: %s", e)

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
