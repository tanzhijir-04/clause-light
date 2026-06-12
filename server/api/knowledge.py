"""知识库接口"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.knowledge import KnowledgeEngine
from server.models.database import KnowledgeRule, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class RuleCreate(BaseModel):
    rule_text: str
    category: str = "通用"
    trigger_keywords: list[str] = []
    confidence: float = 0.5
    source: str = "manual"


class RuleUpdate(BaseModel):
    rule_text: str | None = None
    category: str | None = None
    confidence: float | None = None
    is_active: bool | None = None
    trigger_keywords: list[str] | None = None


@router.get("/rules")
async def list_rules(
    search: str = "",
    category: str = "",
    db: AsyncSession = Depends(get_db),
):
    """规则列表"""
    stmt = select(KnowledgeRule).order_by(KnowledgeRule.created_at.desc())
    result = await db.execute(stmt)
    rules = result.scalars().all()

    response = []
    for r in rules:
        item = {
            "id": r.id,
            "category": r.category,
            "text": r.rule_text,
            "confidence": r.confidence,
            "source": r.source,
            "usageCount": r.usage_count or 0,
            "active": r.is_active,
        }

        if search and search.lower() not in r.rule_text.lower():
            continue
        if category and r.category != category:
            continue

        response.append(item)

    return response


@router.post("/rules")
async def create_rule(
    data: RuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """新增规则"""
    knowledge = KnowledgeEngine(db)
    result = await knowledge.add_rule(data.model_dump())
    return result


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    data: RuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新规则"""
    knowledge = KnowledgeEngine(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    await knowledge.update_rule(rule_id, update_data)
    return {"success": True}


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除规则"""
    knowledge = KnowledgeEngine(db)
    await knowledge.delete_rule(rule_id)
    return {"success": True}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """知识库统计"""
    knowledge = KnowledgeEngine(db)
    return await knowledge.get_stats()


@router.get("/pending")
async def get_pending(db: AsyncSession = Depends(get_db)):
    """待审核规则"""
    knowledge = KnowledgeEngine(db)
    return await knowledge.get_pending()


@router.get("/laws")
async def get_laws(db: AsyncSession = Depends(get_db)):
    """法规列表"""
    knowledge = KnowledgeEngine(db)
    return await knowledge.get_laws()


@router.post("/pending/{rule_id}/approve")
async def approve_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """通过待审核规则"""
    knowledge = KnowledgeEngine(db)
    await knowledge.approve_rule(rule_id)
    return {"success": True}


@router.post("/pending/{rule_id}/reject")
async def reject_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
):
    """拒绝待审核规则"""
    knowledge = KnowledgeEngine(db)
    await knowledge.reject_rule(rule_id)
    return {"success": True}
