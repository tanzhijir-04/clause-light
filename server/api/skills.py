"""Skill 资产 REST API"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.skills import store as skills_store
from server.models.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    triggers: dict = Field(default_factory=dict)
    steps: list = Field(default_factory=list)
    validation: list = Field(default_factory=list)
    resources: list = Field(default_factory=list)
    confidence: float = 0.5
    status: str = "pending"
    version: int = 1


@router.get("")
async def list_skills(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Skill 列表"""
    skills = await skills_store.list_skills(db, status=status)
    return [skills_store.skill_to_dict(s) for s in skills]


@router.post("")
async def create_skill(
    data: SkillCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建 Skill"""
    skill = await skills_store.create_skill(db, data.model_dump())
    await db.commit()
    return skills_store.skill_to_dict(skill)


@router.get("/match")
async def match_skills(
    contract_type: str = "",
    q: str = "",
    limit: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """按合同类型与文本匹配 active Skill"""
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit 须 ≥ 1")
    skills = await skills_store.match_skills(
        db, contract_type=contract_type, text=q, limit=limit
    )
    return [skills_store.skill_to_dict(s) for s in skills]
