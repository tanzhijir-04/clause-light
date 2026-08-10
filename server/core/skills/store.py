"""Skill CRUD 与触发匹配"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.database import Skill

logger = logging.getLogger(__name__)


def _parse_json(raw: str | None, default: Any = None) -> Any:
    """安全解析 JSON 文本字段"""
    if default is None:
        default = {}
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def skill_to_dict(skill: Skill) -> dict:
    """Skill ORM → API 字典"""
    return {
        "id": skill.id,
        "name": skill.name,
        "version": skill.version or 1,
        "status": skill.status or "pending",
        "triggers": _parse_json(skill.triggers, {}),
        "steps": _parse_json(skill.steps, []),
        "validation": _parse_json(skill.validation, []),
        "resources": _parse_json(skill.resources, []),
        "confidence": skill.confidence if skill.confidence is not None else 0.5,
    }


async def list_skills(
    db: AsyncSession,
    *,
    status: str | None = None,
) -> list[Skill]:
    """列出 Skill，可按 status 过滤"""
    stmt = select(Skill).order_by(Skill.updated_at.desc())
    if status:
        stmt = stmt.where(Skill.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_skill(db: AsyncSession, data: dict[str, Any]) -> Skill:
    """创建 Skill 资产"""
    skill = Skill(
        id=data.get("id") or uuid.uuid4().hex,
        name=data["name"],
        version=int(data.get("version") or 1),
        status=data.get("status") or "pending",
        triggers=json.dumps(data.get("triggers") or {}, ensure_ascii=False),
        steps=json.dumps(data.get("steps") or [], ensure_ascii=False),
        validation=json.dumps(data.get("validation") or [], ensure_ascii=False),
        resources=json.dumps(data.get("resources") or [], ensure_ascii=False),
        confidence=float(data.get("confidence", 0.5) or 0.5),
        owner_user_id=data.get("owner_user_id") or "local",
        visibility=data.get("visibility") or "private",
    )
    db.add(skill)
    await db.flush()
    logger.info("创建 Skill: %s (%s)", skill.name, skill.id)
    return skill


async def match_skills(
    db: AsyncSession,
    contract_type: str,
    text: str,
    limit: int = 1,
) -> list[Skill]:
    """
    按合同类型与关键词匹配 active Skill。

    triggers JSON: {"contract_types": [...], "keywords": [...]}
    命中条件：contract_type 在列表中，或任一 keyword 出现在 text 中。
    """
    stmt = select(Skill).where(Skill.status == "active")
    result = await db.execute(stmt)
    skills = list(result.scalars().all())

    q = (text or "").lower()
    ct = (contract_type or "").strip()
    matched: list[tuple[int, Skill]] = []

    for skill in skills:
        triggers = _parse_json(skill.triggers, {})
        if not isinstance(triggers, dict):
            continue

        types = triggers.get("contract_types") or []
        keywords = triggers.get("keywords") or []
        score = 0

        if ct and any(ct == t or ct in str(t) or str(t) in ct for t in types):
            score += 2

        for kw in keywords:
            kw_s = str(kw).strip().lower()
            if kw_s and kw_s in q:
                score += 1

        if score > 0:
            matched.append((score, skill))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in matched[: max(1, limit)]]
