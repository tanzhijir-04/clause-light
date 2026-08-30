"""合同分析接口"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, or_, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import TYPE_EN_MAP, settings
from server.core.agent import ContractAgent
from server.core.document_ingress import ALLOWED_UPLOAD_EXTENSIONS
from server.core.llm import get_llm_gateway
from server.core.risk_display import summarize_risk
from server.models.database import (
    Analysis,
    AsyncSession,
    ClauseAnalysis,
    Contract,
    LegalReference,
    WorkerRiskResult,
    async_session_factory,
    get_db,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contracts", tags=["contracts"])

# 后台分析任务集合：客户端断开后任务仍继续执行，避免结果丢失
_background_tasks: set[asyncio.Task] = set()


@router.get("/")
async def list_contracts(
    search: str = "",
    type: str = "",
    risk: str = "",
    db: AsyncSession = Depends(get_db),
):
    """合同列表，支持 search/type/risk 筛选"""
    stmt = select(Contract).order_by(Contract.created_at.desc())
    result = await db.execute(stmt)
    contracts = result.scalars().all()

    response = []
    for c in contracts:
        # 获取最新分析
        analysis_stmt = (
            select(Analysis)
            .where(Analysis.contract_id == c.id)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        analysis_result = await db.execute(analysis_stmt)
        analysis = analysis_result.scalar_one_or_none()

        # 统计风险分布
        if analysis:
            clause_stmt = select(ClauseAnalysis).where(ClauseAnalysis.analysis_id == analysis.id)
            clause_result = await db.execute(clause_stmt)
            clauses = clause_result.scalars().all()
            display = summarize_risk(
                [cl.risk_level for cl in clauses],
                analysis.status or "pending",
                bool(analysis.review_required)
                or any(bool(cl.review_required) for cl in clauses),
            )
            score = analysis.overall_score or 0
            model = analysis.model_used or ""
            rec = analysis.recommendation or "negotiate_first"
        else:
            display = summarize_risk([])
            score = 0
            model = ""
            rec = "negotiate_first"

        item = {
            "id": c.id,
            "title": c.title or "未命名合同",
            "type": c.type or "其他",
            "typeEn": TYPE_EN_MAP.get(c.type, "other"),
            "score": score,
            "riskLevel": display["riskLevel"],
            "redCount": display["redCount"],
            "yellowCount": display["yellowCount"],
            "greenCount": display["greenCount"],
            "unknownCount": display["unknownCount"],
            "needsReview": display["needsReview"],
            "createdAt": c.created_at.strftime("%Y-%m-%d") if c.created_at else "",
            "status": "analyzed" if analysis else "pending",
            "model": model,
        }

        # 筛选
        if search and search.lower() not in (c.title or "").lower() and search.lower() not in (c.type or "").lower():
            continue
        if type and item["typeEn"] != type:
            continue
        if risk and display["riskLevel"] != risk:
            continue

        response.append(item)

    return response


@router.get("/{contract_id}")
async def get_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    """合同详情 + 分析结果，法条和 Worker 轨迹按分析批量加载。"""
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    analysis_result = await db.execute(
        select(Analysis)
        .where(Analysis.contract_id == contract_id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    clauses = []
    worker_by_clause: dict[str, list[dict]] = {}
    refs_by_id = {}
    if analysis:
        clause_result = await db.execute(
            select(ClauseAnalysis).where(ClauseAnalysis.analysis_id == analysis.id)
        )
        clauses = clause_result.scalars().all()
        worker_result = await db.execute(
            select(WorkerRiskResult).where(WorkerRiskResult.analysis_id == analysis.id)
        )
        for worker in worker_result.scalars().all():
            worker_by_clause.setdefault(worker.clause_number or "", []).append({
                "dimension": worker.dimension,
                "phase": worker.phase,
                "riskLevel": worker.risk_level or "unknown",
                "riskType": worker.risk_type or "",
                "issue": worker.issue or "",
                "severityScore": worker.severity_score,
                "analysisStatus": worker.analysis_status or "completed",
                "needsReview": bool(worker.review_required),
                "reviewReason": worker.review_reason or "",
            })
        citation_ids = set()
        for clause in clauses:
            try:
                values = json.loads(clause.citation_ids or "[]")
            except (json.JSONDecodeError, TypeError):
                values = []
            citation_ids.update(value for value in values if isinstance(value, str))
        if citation_ids:
            refs = await db.execute(select(LegalReference).where(LegalReference.id.in_(citation_ids)))
            refs_by_id = {ref.id: ref for ref in refs.scalars().all()}

    clauses_data = []
    for clause in clauses:
        try:
            citation_values = json.loads(clause.citation_ids or "[]")
        except (json.JSONDecodeError, TypeError):
            citation_values = []
        legal_citations = []
        for citation_id in citation_values if isinstance(citation_values, list) else []:
            ref = refs_by_id.get(citation_id)
            if ref:
                legal_citations.append({
                    "id": ref.id,
                    "lawName": ref.law_name,
                    "articleNumber": ref.article_number or "",
                    "content": ref.content or "",
                    "sourceUrl": ref.source_url,
                    "verifiedAt": ref.verified_at.isoformat() if ref.verified_at else None,
                })
        level = clause.risk_level or "unknown"
        clauses_data.append({
            "id": clause.id,
            "clauseNumber": clause.clause_number or "",
            "clauseTitle": clause.clause_title or "",
            "clauseContent": clause.clause_content or "",
            "riskLevel": level,
            "riskType": clause.risk_type or "",
            "riskSummary": clause.risk_summary or "",
            "plainExplanation": clause.plain_explanation or "",
            "legalBasis": clause.legal_basis or "",
            "severityScore": clause.severity_score or 0,
            "suggestedClause": clause.suggested_clause or "",
            "canNegotiate": clause.can_negotiate or False,
            "userFeedback": clause.user_feedback,
            "analysisStatus": clause.analysis_status or "completed",
            "needsReview": bool(clause.review_required),
            "reviewReason": clause.review_reason or "",
            "sourceStart": clause.source_start,
            "sourceEnd": clause.source_end,
            "legalCitations": legal_citations,
            "workerResults": worker_by_clause.get(clause.clause_number or "", []),
        })

    session_id = ""
    if analysis and analysis.raw_result:
        try:
            raw = json.loads(analysis.raw_result)
            session_id = raw.get("session_id", "") if isinstance(raw, dict) else ""
        except (json.JSONDecodeError, TypeError):
            pass
    review_reasons = {}
    if analysis and analysis.review_reason:
        try:
            parsed = json.loads(analysis.review_reason)
            review_reasons = parsed if isinstance(parsed, dict) else {"analysis": [analysis.review_reason]}
        except (json.JSONDecodeError, TypeError):
            review_reasons = {"analysis": [analysis.review_reason]}
    display = summarize_risk(
        [clause["riskLevel"] for clause in clauses_data],
        analysis.status if analysis and analysis.status else "pending",
        bool(analysis and analysis.review_required)
        or any(c["needsReview"] for c in clauses_data),
    )
    return {
        "id": contract.id,
        "title": contract.title or "未命名合同",
        "type": contract.type or "其他",
        "typeEn": TYPE_EN_MAP.get(contract.type, "other"),
        "score": analysis.overall_score if analysis else None,
        "riskLevel": display["riskLevel"],
        "redCount": display["redCount"], "yellowCount": display["yellowCount"],
        "greenCount": display["greenCount"], "unknownCount": display["unknownCount"],
        "createdAt": contract.created_at.strftime("%Y-%m-%d") if contract.created_at else "",
        "status": "analyzed" if analysis else "pending",
        "model": analysis.model_used if analysis else "",
        "summary": analysis.summary if analysis else "",
        "recommendation": analysis.recommendation if analysis else "",
        "fullText": contract.ocr_text or "",
        "sessionId": session_id,
        "analysisStatus": analysis.status if analysis else "pending",
        "needsReview": display["needsReview"],
        "reviewReasons": review_reasons,
        "processingMode": analysis.processing_mode if analysis else None,
        "clauses": clauses_data,
    }


async def persist_analysis_result(
    contract_id: str,
    result,
    session_factory=None,
) -> str | None:
    """保存分析结果到数据库（独立 session）；成功返回 None，失败返回错误信息。

    在后台任务内执行，即使 SSE 连接断开也会完成写入。
    session_factory 可注入，便于测试替换内存数据库。
    """
    if session_factory is None:
        session_factory = async_session_factory

    try:
        async with session_factory() as session:
            analysis_status = getattr(result, "analysis_status", "completed")
            if not isinstance(analysis_status, str) or not analysis_status:
                analysis_status = "completed"
            review_reasons = getattr(result, "review_reasons", {})
            if not isinstance(review_reasons, dict):
                review_reasons = {}
            processing_mode = getattr(result, "processing_mode", "local")
            if not isinstance(processing_mode, str) or not processing_mode:
                processing_mode = "local"
            storage_source = processing_mode if processing_mode in {"local", "remote"} else "local"
            worker_risks = getattr(result, "worker_risks", [])
            if not isinstance(worker_risks, list):
                worker_risks = []

            # 更新合同记录
            await session.execute(
                sa_update(Contract)
                .where(Contract.id == contract_id)
                .values(
                    ocr_text=result.ocr_text or "",
                    type=result.contract_type,
                    updated_at=datetime.now(timezone.utc),
                )
            )

            # 保存分析结果
            if result.contract_id:
                analysis = Analysis(
                    id=result.contract_id,
                    contract_id=contract_id,
                    model_used=result.model_used,
                    overall_score=result.overall_score,
                    summary=result.summary,
                    recommendation=result.recommendation,
                    raw_result=json.dumps(
                        {
                            "clauses": result.clauses,
                            "session_id": result.session_id
                            if isinstance(getattr(result, "session_id", None), str)
                            else "",
                        },
                        ensure_ascii=False,
                    ),
                    source=storage_source,
                    status=analysis_status,
                    review_required=bool(review_reasons),
                    review_reason=json.dumps(
                        review_reasons, ensure_ascii=False
                    ),
                    processing_mode=processing_mode,
                )
                session.add(analysis)

                for clause in result.clauses:
                    clause_analysis = ClauseAnalysis(
                        id=uuid.uuid4().hex,
                        analysis_id=analysis.id,
                        clause_number=clause.get("clause_number", ""),
                        clause_title=clause.get("title", ""),
                        clause_content=clause.get("content", ""),
                        risk_level=clause.get("risk_level", "green"),
                        risk_type=clause.get("risk_type", ""),
                        risk_summary=clause.get("risk_summary", ""),
                        plain_explanation=clause.get("plain_explanation", ""),
                        legal_basis=clause.get("legal_basis", ""),
                        severity_score=clause.get("severity_score", 1),
                        suggested_clause=clause.get("suggested_clause", ""),
                        can_negotiate=clause.get("can_negotiate", False),
                        analysis_status=clause.get("analysis_status", "completed"),
                        review_required=clause.get("needs_review", False),
                        review_reason=clause.get("review_reason", ""),
                        source_start=clause.get("source_start", -1),
                        source_end=clause.get("source_end", -1),
                        citation_ids=json.dumps(
                            clause.get("citation_ids", []), ensure_ascii=False
                        ),
                    )
                    session.add(clause_analysis)

                for worker in worker_risks:
                    session.add(WorkerRiskResult(
                        id=uuid.uuid4().hex,
                        analysis_id=analysis.id,
                        clause_number=worker.get("clause_id", ""),
                        dimension=worker.get("dimension", "general"),
                        phase=worker.get("phase", "initial"),
                        risk_level=worker.get("risk_level"),
                        risk_type=worker.get("risk_type", ""),
                        issue=worker.get("issue", ""),
                        unfavorable_to=worker.get("unfavorable_to", ""),
                        severity_score=worker.get("severity"),
                        suggestion=worker.get("suggestion", ""),
                        legal_basis=worker.get("legal_basis", ""),
                        citation_ids=json.dumps(
                            worker.get("citation_ids", []), ensure_ascii=False
                        ),
                        analysis_status=worker.get("analysis_status", "completed"),
                        failure_reason=worker.get("failure_reason", ""),
                        review_required=worker.get("review_required", False),
                        review_reason=worker.get("review_reason", ""),
                    ))

            await session.commit()
        return None
    except Exception as e:
        logger.error("保存分析结果失败: %s", e)
        return f"结果保存失败: {e}"


@router.post("/analyze")
async def analyze_contract(
    file: UploadFile = File(...),
    contract_type: str = Form(default=""),
    allow_remote_processing: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
):
    """上传并分析合同（SSE 流式返回进度）"""
    # 验证文件
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="不支持的文件格式，请上传 PDF、办公文档（如 Word/Excel）或图片",
        )

    processing_plan = get_llm_gateway().get_processing_plan(task="analysis")
    if processing_plan.processing_mode == "remote" and not allow_remote_processing:
        raise HTTPException(
            status_code=400,
            detail="当前分析将把合同文本发送到已配置的远程模型服务。请确认后重新提交，或切换到本地 Ollama。",
        )

    # 保存文件
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{ext}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过限制（20MB）")

    with open(file_path, "wb") as f:
        f.write(content)

    # 创建合同记录（使用独立 session，不依赖请求级 session）
    contract_id = file_id
    contract_title = os.path.splitext(file.filename)[0]
    async with async_session_factory() as session:
        contract = Contract(
            id=contract_id,
            title=contract_title,
            type=contract_type or "其他",
            source_file=file_path,
        )
        session.add(contract)
        await session.commit()

    async def event_stream():
        """SSE 事件流：进度推送 + 最终结果"""
        agent = ContractAgent()
        progress_queue: asyncio.Queue = asyncio.Queue()

        async def on_progress(step: int, total: int, message: str) -> None:
            """Agent 回调：将进度事件放入队列"""
            await progress_queue.put({"type": "progress", "step": step, "total": total, "message": message})

        def on_embedding_progress(current: int, total: int, desc: str) -> None:
            """Embedding 模型下载进度回调（同步，在线程池中调用）"""
            # 构建进度消息
            if total > 0:
                # 格式化下载进度
                if current >= 1024 * 1024:
                    # 已下载超过 1MB，显示 MB 单位
                    mb_current = current / 1024 / 1024
                    mb_total = total / 1024 / 1024
                    msg = f"下载知识库模型: {mb_current:.1f}/{mb_total:.1f}MB"
                else:
                    msg = f"下载知识库模型: {current}/{total}"
            else:
                msg = f"下载知识库模型: {desc or '准备中...'}"

            # 放入队列（线程安全）
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(progress_queue.put({
                        "type": "progress",
                        "step": 2,
                        "total": 5,
                        "message": msg,
                        "substep": desc,
                    }))
            except Exception:
                pass

        # 设置 embedding 下载进度回调
        from server.core import embedding
        embedding.set_progress_callback(on_embedding_progress)

        async def run_agent():
            """在后台运行 Agent 并保存结果，完成后放入结束标记"""
            try:
                result = await agent.analyze(
                    file_path=file_path,
                    contract_type_hint=contract_type if contract_type else None,
                    on_step=on_progress,
                )
                # 保存结果在后台任务内完成，客户端断开也不丢失
                if getattr(result, "contract_id", ""):
                    save_error = await persist_analysis_result(contract_id, result)
                    if save_error:
                        result.error = save_error
                return result
            except Exception as e:
                logger.error("Agent 分析异常: %s", e)
                return type('obj', (object,), {'error': f'合同分析异常: {e}', 'ocr_text': '', 'contract_id': ''})()
            finally:
                # 清除 embedding 进度回调
                embedding._clear_progress_callback()
                await progress_queue.put(None)  # 结束标记

        # 启动 Agent 任务
        agent_task = asyncio.create_task(run_agent())

        # 从队列中消费进度事件并推送
        try:
            while True:
                event = await progress_queue.get()
                if event is None:
                    break
                yield _sse_event(event)
        except asyncio.CancelledError:
            # 客户端断开：不取消后台任务，让分析继续完成后保存结果
            _background_tasks.add(agent_task)
            agent_task.add_done_callback(_background_tasks.discard)
            return

        # 等待 Agent 完成并获取结果
        result = await agent_task

        # 分析失败
        if result.error:
            logger.warning("合同分析失败: %s", result.error)
            yield _sse_event({"type": "error", "message": result.error})
            return

        # 推送最终结果
        analysis_status = getattr(result, "analysis_status", "pending")
        if not isinstance(analysis_status, str) or not analysis_status:
            analysis_status = "pending"
        review_reasons = getattr(result, "review_reasons", {})
        if not isinstance(review_reasons, dict):
            review_reasons = {}
        display = summarize_risk(
            [clause.get("risk_level") for clause in result.clauses],
            analysis_status,
            bool(review_reasons)
            or any(clause.get("needs_review", False) for clause in result.clauses),
        )
        yield _sse_event({
            "type": "result",
            "contractId": contract_id,
            "score": result.overall_score,
            **display,
            "analysisStatus": analysis_status,
            "reviewReasons": review_reasons,
            "sessionId": result.session_id
            if isinstance(getattr(result, "session_id", None), str)
            else "",
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse_event(data: dict) -> str:
    """格式化 SSE 事件"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{contract_id}/feedback")
async def submit_feedback(
    contract_id: str,
    clause_analysis_id: str = Form(...),
    feedback: str = Form(...),  # correct / incorrect
    db: AsyncSession = Depends(get_db),
):
    """提交用户反馈，若反馈为"incorrect"则触发自动学习"""
    stmt = select(ClauseAnalysis).where(ClauseAnalysis.id == clause_analysis_id)
    result = await db.execute(stmt)
    clause = result.scalar_one_or_none()
    if not clause:
        raise HTTPException(status_code=404, detail="条款分析不存在")

    clause.user_feedback = feedback

    # 如果用户认为分析结果"不正确"，触发自动学习管道
    auto_learned = None
    if feedback == "incorrect":
        from server.core.knowledge import KnowledgeEngine

        engine = KnowledgeEngine(db)
        auto_learned = await engine.trigger_auto_learning(clause)

    await db.commit()

    return {
        "success": True,
        "autoLearned": auto_learned is not None,
    }


@router.put("/{contract_id}")
async def update_contract(
    contract_id: str,
    data: dict = {},
    db: AsyncSession = Depends(get_db),
):
    """更新合同信息（如合同名称、类型等）"""
    stmt = select(Contract).where(Contract.id == contract_id)
    result = await db.execute(stmt)
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 更新允许的字段
    if "title" in data:
        contract.title = data["title"]
    if "type" in data:
        contract.type = data["type"]

    await db.commit()

    return {"success": True, "message": "合同已更新"}


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除合同及其关联的分析记录和条款分析"""
    # 验证合同是否存在
    stmt = select(Contract).where(Contract.id == contract_id)
    result = await db.execute(stmt)
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 查询该合同的所有分析 ID（用于级联删除条款分析）
    analysis_stmt = select(Analysis.id).where(Analysis.contract_id == contract_id)
    analysis_result = await db.execute(analysis_stmt)
    analysis_ids = [row[0] for row in analysis_result.all()]

    # 1. 删除 Worker 轨迹（依赖 analysis_id）
    if analysis_ids:
        await db.execute(
            delete(WorkerRiskResult).where(WorkerRiskResult.analysis_id.in_(analysis_ids))
        )

    # 2. 删除条款分析（依赖 analysis_id）
    if analysis_ids:
        await db.execute(
            delete(ClauseAnalysis).where(ClauseAnalysis.analysis_id.in_(analysis_ids))
        )

    # 3. 删除分析记录（依赖 contract_id）
    await db.execute(
        delete(Analysis).where(Analysis.contract_id == contract_id)
    )

    # 4. 删除合同记录
    await db.execute(
        delete(Contract).where(Contract.id == contract_id)
    )

    # 5. 删除上传的源文件（如果存在）
    if contract.source_file and os.path.exists(contract.source_file):
        try:
            os.remove(contract.source_file)
        except OSError:
            logger.warning("无法删除源文件: %s", contract.source_file)

    await db.commit()

    return {"success": True, "message": "合同已删除"}
