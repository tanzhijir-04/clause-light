"""分层记忆 REST API"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.distill import activate
from server.core.memory.kernel import MemoryKernel
from server.models.database import (
    KnowledgeRule,
    MemoryAtom,
    Skill,
    WikiPage,
    get_db,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])

_PENDING_TYPES = ("rule", "atom", "skill", "wiki")


class SessionCreate(BaseModel):
    contract_id: str | None = None
    contract_type: str | None = None


class FeedbackBody(BaseModel):
    atom_id: str | None = None
    session_id: str | None = None
    confirm: bool | None = None
    payload: dict | None = None


def _pending_item(
    *,
    asset_type: str,
    asset_id: str,
    summary: str,
    confidence: float | None = None,
    extra: dict | None = None,
) -> dict:
    """统一待审项结构"""
    item = {
        "asset_type": asset_type,
        "id": asset_id,
        "summary": summary,
        "confidence": confidence if confidence is not None else 0.5,
        "status": "pending",
    }
    if extra:
        item.update(extra)
    return item


@router.post("/sessions")
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建记忆会话"""
    k = MemoryKernel(db)
    sid = await k.start_session(data.contract_id, data.contract_type)
    await db.commit()
    return {"id": sid}


@router.get("/atoms")
async def list_atoms(
    q: str = "",
    status: str = "active",
    db: AsyncSession = Depends(get_db),
):
    """L1 记忆原子列表 / 搜索"""
    stmt = select(MemoryAtom).order_by(MemoryAtom.updated_at.desc())
    if status:
        stmt = stmt.where(MemoryAtom.status == status)
    result = await db.execute(stmt)
    atoms = result.scalars().all()

    response = []
    q_lower = q.lower() if q else ""
    for a in atoms:
        if q_lower and q_lower not in (a.content or "").lower():
            continue
        response.append(
            {
                "id": a.id,
                "content": a.content,
                "kind": a.kind,
                "contract_type": a.contract_type,
                "confidence": a.confidence,
                "status": a.status,
                "confirm_count": a.confirm_count or 0,
                "reject_count": a.reject_count or 0,
                "session_id": a.session_id,
            }
        )
    return response


@router.post("/feedback")
async def feedback(
    data: FeedbackBody,
    db: AsyncSession = Depends(get_db),
):
    """用户纠错 / 确认反馈"""
    k = MemoryKernel(db)
    result = await k.record_feedback(
        atom_id=data.atom_id,
        session_id=data.session_id,
        payload=data.payload or {},
        confirm=data.confirm,
    )
    await db.commit()
    return {"success": True, **result}


@router.get("/pending")
async def list_pending(db: AsyncSession = Depends(get_db)):
    """聚合 rules / atoms / skills / wiki 中 status=pending 的资产"""
    items: list[dict] = []

    rules = (
        await db.execute(select(KnowledgeRule).where(KnowledgeRule.status == "pending"))
    ).scalars().all()
    for r in rules:
        items.append(
            _pending_item(
                asset_type="rule",
                asset_id=r.id,
                summary=r.rule_text or "",
                confidence=r.confidence,
                extra={"category": r.category},
            )
        )

    atoms = (
        await db.execute(select(MemoryAtom).where(MemoryAtom.status == "pending"))
    ).scalars().all()
    for a in atoms:
        items.append(
            _pending_item(
                asset_type="atom",
                asset_id=a.id,
                summary=a.content or "",
                confidence=a.confidence,
                extra={"kind": a.kind},
            )
        )

    skills = (
        await db.execute(select(Skill).where(Skill.status == "pending"))
    ).scalars().all()
    for s in skills:
        items.append(
            _pending_item(
                asset_type="skill",
                asset_id=s.id,
                summary=s.name or "",
                confidence=s.confidence,
            )
        )

    pages = (
        await db.execute(select(WikiPage).where(WikiPage.status == "pending"))
    ).scalars().all()
    for p in pages:
        items.append(
            _pending_item(
                asset_type="wiki",
                asset_id=p.id,
                summary=p.title or p.slug or "",
                confidence=p.confidence,
                extra={"slug": p.slug},
            )
        )

    return items


async def _run_pending_action(
    db: AsyncSession,
    asset_type: str,
    asset_id: str,
    action: str,
) -> dict:
    """执行 approve / reject / rollback"""
    if asset_type not in _PENDING_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的资产类型: {asset_type}")

    try:
        if action == "approve":
            await activate.approve(db, asset_type, asset_id)
        elif action == "reject":
            await activate.reject(db, asset_type, asset_id)
        elif action == "rollback":
            await activate.rollback(db, asset_type, asset_id)
        else:
            raise HTTPException(status_code=400, detail=f"未知操作: {action}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    await db.commit()
    return {"success": True, "asset_type": asset_type, "asset_id": asset_id, "action": action}


@router.post("/pending/{asset_type}/{asset_id}/approve")
async def approve_pending(
    asset_type: str,
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """审核通过 → active"""
    return await _run_pending_action(db, asset_type, asset_id, "approve")


@router.post("/pending/{asset_type}/{asset_id}/reject")
async def reject_pending(
    asset_type: str,
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """审核拒绝 → disabled"""
    return await _run_pending_action(db, asset_type, asset_id, "reject")


@router.post("/pending/{asset_type}/{asset_id}/rollback")
async def rollback_pending(
    asset_type: str,
    asset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """回滚 → rolled_back"""
    return await _run_pending_action(db, asset_type, asset_id, "rollback")
