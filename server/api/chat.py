"""合同多轮追问 Chat API"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.llm import get_llm_gateway
from server.core.memory.kernel import MemoryKernel
from server.models.database import Analysis, Contract, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/contracts", tags=["chat"])

_CONTRACT_EXCERPT_CHARS = 4000


class ChatBody(BaseModel):
    """追问请求体"""

    message: str = Field(..., min_length=1)
    session_id: str | None = None


def _build_analysis_summary(analysis: Analysis | None) -> str:
    """将最新分析压缩为 prompt 可用摘要"""
    if analysis is None:
        return "（尚无分析结果）"
    parts = []
    if analysis.overall_score is not None:
        parts.append(f"综合评分：{analysis.overall_score}")
    if analysis.recommendation:
        parts.append(f"建议：{analysis.recommendation}")
    if analysis.summary:
        parts.append(f"摘要：{analysis.summary}")
    return "\n".join(parts) if parts else "（分析结果为空）"


def _format_memory_hits(hits: list) -> str:
    """格式化记忆召回命中"""
    if not hits:
        return "（无相关记忆）"
    lines = []
    for h in hits:
        layer = getattr(h, "layer", "?")
        text = (getattr(h, "text", "") or "").strip()
        if text:
            lines.append(f"- [{layer}] {text}")
    return "\n".join(lines) if lines else "（无相关记忆）"


def _build_messages(
    *,
    title: str,
    contract_type: str,
    excerpt: str,
    analysis_summary: str,
    memory_text: str,
    user_message: str,
) -> list[dict]:
    """组装追问 system + user 消息"""
    system = (
        "你是合同风险审查助手「合同红绿灯」。"
        "请基于给定的合同摘录、分析结果与相关记忆，用通俗中文回答用户追问。"
        "不要编造合同中不存在的条款；不确定时明确说明。"
    )
    context = (
        f"【合同】{title}（类型：{contract_type}）\n\n"
        f"【合同摘录】\n{excerpt}\n\n"
        f"【分析摘要】\n{analysis_summary}\n\n"
        f"【相关记忆】\n{memory_text}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{context}\n\n【用户追问】\n{user_message}"},
    ]


@router.post("/{contract_id}/chat")
async def chat_contract(
    contract_id: str,
    body: ChatBody,
    db: AsyncSession = Depends(get_db),
):
    """针对已入库合同的多轮追问，复用/创建 L0 session 并写入对话事件"""
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

    kernel = MemoryKernel(db)
    session_id = body.session_id
    if not session_id:
        session_id = await kernel.start_session(contract.id, contract.type)

    await kernel.append_event(
        session_id,
        "user_message",
        {"message": body.message, "contract_id": contract_id},
    )

    hits = await kernel.retrieve(
        body.message,
        contract_type=contract.type,
    )

    ocr_text = contract.ocr_text or ""
    excerpt = ocr_text[:_CONTRACT_EXCERPT_CHARS]
    analysis_summary = _build_analysis_summary(analysis)
    memory_text = _format_memory_hits(hits)
    messages = _build_messages(
        title=contract.title or "未命名合同",
        contract_type=contract.type or "其他",
        excerpt=excerpt or "（无原文）",
        analysis_summary=analysis_summary,
        memory_text=memory_text,
        user_message=body.message,
    )

    llm = get_llm_gateway()
    resp = await llm.chat(messages, task="explanation")
    reply = (resp.content or "").strip() or "暂时无法回答，请稍后重试。"

    await kernel.append_event(
        session_id,
        "assistant_message",
        {"message": reply, "contract_id": contract_id},
    )
    await db.commit()

    return {"reply": reply, "session_id": session_id}
