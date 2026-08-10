"""Agent 记忆 / Wiki / Skill 工具包装 — 预算裁剪后注入 Pipeline"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.core.memory.kernel import MemoryKernel
from server.core.memory.models import MemoryHit, RetrieveBudget
from server.core.skills import store as skills_store
from server.core.wiki import store as wiki_store

logger = logging.getLogger(__name__)


@dataclass
class ToolBundle:
    """冲突路径工具结果（memory / wiki / skill 文本）"""

    memory_text: str = ""
    wiki_text: str = ""
    skill_text: str = ""


def _truncate(text: str, budget: int | None = None) -> str:
    """按字符预算截断文本"""
    limit = budget if budget is not None else settings.MEMORY_RETRIEVE_CHAR_BUDGET
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit]


def _format_hits(hits: list[MemoryHit], heading: str) -> str:
    """MemoryHit 列表 → Markdown 小节"""
    lines = [h.text.strip() for h in hits if h.text and h.text.strip()]
    if not lines:
        return ""
    body = "\n".join(f"- {line}" for line in lines)
    return f"### {heading}\n{body}"


def _join_sections(*sections: str) -> str:
    """拼接非空 Markdown 小节"""
    parts = [s.strip() for s in sections if s and s.strip()]
    return "\n\n".join(parts)


def _retrieve_queries(contract_type: str, query: str) -> list[str]:
    """生成短召回 query：合同类型优先，避免长全文无法关键词命中。"""
    seen: set[str] = set()
    out: list[str] = []
    for q in (contract_type or "", (query or "").strip()[:40]):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out or [""]


async def build_loadout(
    db: AsyncSession,
    *,
    contract_type: str,
    query: str,
) -> str:
    """L3+L2 开场文本，已裁预算。失败返回空串。"""
    try:
        kernel = MemoryKernel(db)
        budget = RetrieveBudget.default()
        budget.max_l1 = 0  # 开场只取人格与场景
        seen_ids: set[str] = set()
        hits: list[MemoryHit] = []
        for q in _retrieve_queries(contract_type, query):
            for h in await kernel.retrieve(
                q,
                contract_type=contract_type or None,
                budget=budget,
            ):
                if h.id not in seen_ids:
                    seen_ids.add(h.id)
                    hits.append(h)
        l3 = [h for h in hits if h.layer == "l3"]
        l2 = [h for h in hits if h.layer == "l2"]
        text = _join_sections(
            _format_hits(l3, "人格记忆 (L3)"),
            _format_hits(l2, "场景记忆 (L2)"),
        )
        return _truncate(text)
    except Exception as e:
        logger.warning("build_loadout 失败，降级为空: %s", e)
        return ""


async def build_stage_context(
    db: AsyncSession,
    *,
    contract_type: str,
    query: str,
    kb_rules: list[str],
) -> str:
    """L1 + 规则 + 匹配 Skill，已裁预算。失败时尽量保留规则文本。"""
    sections: list[str] = []
    try:
        kernel = MemoryKernel(db)
        budget = RetrieveBudget.default()
        budget.max_l2 = 0
        budget.max_l3 = 0
        seen_ids: set[str] = set()
        hits: list[MemoryHit] = []
        for q in _retrieve_queries(contract_type, query):
            for h in await kernel.retrieve(
                q,
                contract_type=contract_type or None,
                budget=budget,
            ):
                if h.id not in seen_ids:
                    seen_ids.add(h.id)
                    hits.append(h)
        atom_section = _format_hits(
            [h for h in hits if h.layer == "l1"],
            "原子记忆 (L1)",
        )
        if atom_section:
            sections.append(atom_section)
    except Exception as e:
        logger.warning("stage 记忆召回失败: %s", e)

    if kb_rules:
        rules_body = "\n".join(f"- {r}" for r in kb_rules if r)
        if rules_body:
            sections.append(f"### 知识库规则\n{rules_body}")

    try:
        skills = await skills_store.match_skills(
            db,
            contract_type or "",
            query or "",
            limit=1,
        )
        if skills:
            skill = skills[0]
            from server.core.skills.store import skill_to_dict

            data = skill_to_dict(skill)
            steps = data.get("steps") or []
            step_lines = []
            for s in steps:
                if isinstance(s, str):
                    step_lines.append(f"- {s}")
                elif isinstance(s, dict):
                    step_lines.append(f"- {s.get('text') or s.get('step') or s}")
            body = "\n".join(step_lines) if step_lines else f"- {data.get('name', '')}"
            sections.append(f"### 匹配 Skill：{data.get('name', '')}\n{body}")
    except Exception as e:
        logger.warning("Skill 匹配失败: %s", e)

    return _truncate(_join_sections(*sections))


async def run_conflict_tools(
    db: AsyncSession,
    *,
    query: str,
    contract_type: str,
) -> ToolBundle:
    """冲突时补充 memory / wiki / skill；失败返回空 bundle。"""
    bundle = ToolBundle()
    try:
        kernel = MemoryKernel(db)
        hits = await kernel.retrieve(
            query or contract_type or "",
            contract_type=contract_type or None,
        )
        memory = _format_hits(hits, "冲突补充记忆")
        bundle.memory_text = _truncate(memory, settings.MEMORY_RETRIEVE_CHAR_BUDGET // 2)
    except Exception as e:
        logger.warning("冲突路径 memory_search 失败: %s", e)

    try:
        pages = await wiki_store.search_pages(db, query or contract_type or "", limit=3)
        if pages:
            lines = []
            for p in pages:
                snippet = (p.body or "")[:200]
                lines.append(f"- **{p.title}**: {snippet}")
            bundle.wiki_text = _truncate(
                f"### Wiki\n" + "\n".join(lines),
                settings.MEMORY_RETRIEVE_CHAR_BUDGET // 3,
            )
    except Exception as e:
        logger.warning("冲突路径 wiki_search 失败: %s", e)

    try:
        skills = await skills_store.match_skills(
            db,
            contract_type or "",
            query or "",
            limit=1,
        )
        if skills:
            from server.core.skills.store import skill_to_dict

            data = skill_to_dict(skills[0])
            bundle.skill_text = _truncate(
                f"### Skill：{data.get('name', '')}\n{data.get('steps') or []}",
                settings.MEMORY_RETRIEVE_CHAR_BUDGET // 4,
            )
    except Exception as e:
        logger.warning("冲突路径 load_skill 失败: %s", e)

    return bundle
