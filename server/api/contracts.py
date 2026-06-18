"""合同分析接口"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import TYPE_EN_MAP, settings
from server.core.agent import ContractAgent
from server.core.llm import get_llm_gateway
from server.core.ocr import get_ocr_engine
from server.models.database import (
    Analysis,
    AsyncSession,
    ClauseAnalysis,
    Contract,
    get_db,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contracts", tags=["contracts"])


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
            red = sum(1 for cl in clauses if cl.risk_level == "red")
            yellow = sum(1 for cl in clauses if cl.risk_level == "yellow")
            green = sum(1 for cl in clauses if cl.risk_level == "green")
            score = analysis.overall_score or 0
            model = analysis.model_used or ""
            rec = analysis.recommendation or "negotiate_first"
        else:
            red = yellow = green = 0
            score = 0
            model = ""
            rec = "negotiate_first"

        # 风险等级
        if red > 0:
            risk_level = "red"
        elif yellow > 0:
            risk_level = "yellow"
        else:
            risk_level = "green"

        item = {
            "id": c.id,
            "title": c.title or "未命名合同",
            "type": c.type or "其他",
            "typeEn": TYPE_EN_MAP.get(c.type, "other"),
            "score": score,
            "riskLevel": risk_level,
            "redCount": red,
            "yellowCount": yellow,
            "greenCount": green,
            "createdAt": c.created_at.strftime("%Y-%m-%d") if c.created_at else "",
            "status": "analyzed" if analysis else "pending",
            "model": model,
        }

        # 筛选
        if search and search.lower() not in (c.title or "").lower() and search.lower() not in (c.type or "").lower():
            continue
        if type and item["typeEn"] != type:
            continue
        if risk and risk_level != risk:
            continue

        response.append(item)

    return response


@router.get("/{contract_id}")
async def get_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    """合同详情 + 分析结果"""
    stmt = select(Contract).where(Contract.id == contract_id)
    result = await db.execute(stmt)
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="合同不存在")

    # 获取最新分析
    analysis_stmt = (
        select(Analysis)
        .where(Analysis.contract_id == contract_id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    analysis_result = await db.execute(analysis_stmt)
    analysis = analysis_result.scalar_one_or_none()

    # 获取条款分析
    clauses_data = []
    red = yellow = green = 0
    if analysis:
        clause_stmt = (
            select(ClauseAnalysis).where(ClauseAnalysis.analysis_id == analysis.id)
        )
        clause_result = await db.execute(clause_stmt)
        clauses = clause_result.scalars().all()
        for cl in clauses:
            clauses_data.append({
                "id": cl.id,
                "clauseNumber": cl.clause_number or "",
                "clauseTitle": cl.clause_title or "",
                "clauseContent": cl.clause_content or "",
                "riskLevel": cl.risk_level or "green",
                "riskType": cl.risk_type or "",
                "riskSummary": cl.risk_summary or "",
                "plainExplanation": cl.plain_explanation or "",
                "legalBasis": cl.legal_basis or "",
                "severityScore": cl.severity_score or 0,
                "suggestedClause": cl.suggested_clause or "",
                "canNegotiate": cl.can_negotiate or False,
                "userFeedback": cl.user_feedback,
            })
            if cl.risk_level == "red":
                red += 1
            elif cl.risk_level == "yellow":
                yellow += 1
            else:
                green += 1

    return {
        "id": contract.id,
        "title": contract.title or "未命名合同",
        "type": contract.type or "其他",
        "typeEn": TYPE_EN_MAP.get(contract.type, "other"),
        "score": analysis.overall_score if analysis else 0,
        "riskLevel": "red" if red > 0 else ("yellow" if yellow > 0 else "green"),
        "redCount": red,
        "yellowCount": yellow,
        "greenCount": green,
        "createdAt": contract.created_at.strftime("%Y-%m-%d") if contract.created_at else "",
        "status": "analyzed" if analysis else "pending",
        "model": analysis.model_used if analysis else "",
        "summary": analysis.summary if analysis else "",
        "recommendation": analysis.recommendation if analysis else "",
        "fullText": contract.ocr_text or "",
        "clauses": clauses_data,
    }


@router.post("/analyze")
async def analyze_contract(
    file: UploadFile = File(...),
    contract_type: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """上传并分析合同"""
    # 验证文件
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 PDF 或图片")

    # 保存文件
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{ext}")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过限制（20MB）")

    with open(file_path, "wb") as f:
        f.write(content)

    # 创建合同记录
    contract = Contract(
        id=file_id,
        title=os.path.splitext(file.filename)[0],
        type=contract_type or "其他",
        source_file=file_path,
    )
    db.add(contract)
    await db.flush()

    # 执行 7 步分析
    agent = ContractAgent()
    try:
        result = await agent.analyze(
            file_path=file_path,
            contract_type_hint=contract_type if contract_type else None,
        )
    except Exception as e:
        logger.error("合同分析异常: %s", e)
        await db.commit()
        return {
            "success": False,
            "contractId": contract.id,
            "error": f"合同分析异常: {str(e)}",
        }

    # 检查分析是否失败（问题 5 修复：不再返回 success:true + score:0）
    if result.error:
        logger.warning("合同分析失败: %s", result.error)
        await db.commit()
        return {
            "success": False,
            "contractId": contract.id,
            "error": result.error,
        }

    # 保存 OCR 原文到合同记录（用于原文标注视图）
    if result.ocr_text:
        contract.ocr_text = result.ocr_text

    # 保存分析结果
    if result.contract_id:
        analysis = Analysis(
            id=result.contract_id,
            contract_id=contract.id,
            model_used=result.model_used,
            overall_score=result.overall_score,
            summary=result.summary,
            recommendation=result.recommendation,
            raw_result=json.dumps({"clauses": result.clauses}, ensure_ascii=False),
            source="local",
        )
        db.add(analysis)

        # 保存条款分析
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
            )
            db.add(clause_analysis)

        # 更新合同标题和类型
        contract.type = result.contract_type
        contract.updated_at = datetime.now(timezone.utc)

    # 显式提交，确保合同记录和分析结果都持久化
    await db.commit()

    return {
        "success": True,
        "contractId": contract.id,
        "score": result.overall_score,
        "riskLevel": "red" if result.red_count > 0 else ("yellow" if result.yellow_count > 0 else "green"),
    }


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

    # 1. 删除条款分析（依赖 analysis_id）
    if analysis_ids:
        await db.execute(
            delete(ClauseAnalysis).where(ClauseAnalysis.analysis_id.in_(analysis_ids))
        )

    # 2. 删除分析记录（依赖 contract_id）
    await db.execute(
        delete(Analysis).where(Analysis.contract_id == contract_id)
    )

    # 3. 删除合同记录
    await db.execute(
        delete(Contract).where(Contract.id == contract_id)
    )

    # 4. 删除上传的源文件（如果存在）
    if contract.source_file and os.path.exists(contract.source_file):
        try:
            os.remove(contract.source_file)
        except OSError:
            logger.warning("无法删除源文件: %s", contract.source_file)

    await db.commit()

    return {"success": True, "message": "合同已删除"}
