"""分层记忆 REST API"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.memory.kernel import MemoryKernel
from server.models.database import MemoryAtom, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


class SessionCreate(BaseModel):
    contract_id: str | None = None
    contract_type: str | None = None


class FeedbackBody(BaseModel):
    atom_id: str | None = None
    session_id: str | None = None
    confirm: bool | None = None
    payload: dict | None = None


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
