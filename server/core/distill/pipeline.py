"""Distill Pipeline — 分析后异步提炼候选记忆资产"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.distill import activate
from server.core.knowledge import sync_rule_is_active
from server.core.memory import store as memory_store
from server.core.prompts.distill import build_distill_messages
from server.models.database import KnowledgeRule, Skill, WikiPage

logger = logging.getLogger(__name__)

_EMPTY = {"rules": 0, "atoms": 0, "skills": 0, "wiki": 0}


def _parse_json_content(content: str) -> dict | None:
    """从 LLM 文本提取 JSON 对象，失败返回 None"""
    if not content or not content.strip():
        return None
    text = content.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def _is_similar(a: str, b: str) -> bool:
    """简单子串相似：任一方包含另一方（长度≥4）"""
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    if len(a) < 4 and len(b) < 4:
        return a == b
    return a in b or b in a


async def _merge_or_create_atom(
    db: AsyncSession,
    *,
    session_id: str,
    contract_type: str,
    item: dict[str, Any],
) -> str | None:
    """去重后写入 L1 atom，返回 id。

    - pending：合并置信度并返回，供 maybe_activate 晋升
    - active：仅抬升 confidence / confirm_count，不改 status
    - rolled_back / disabled：不合并，另建 pending
    """
    content = (item.get("content") or "").strip()
    if not content:
        return None
    confidence = float(item.get("confidence", 0.5) or 0.5)

    from server.models.database import MemoryAtom

    existing = (await db.execute(select(MemoryAtom))).scalars().all()
    for atom in existing:
        if not _is_similar(atom.content, content):
            continue
        status = atom.status or "pending"
        if status in ("rolled_back", "disabled"):
            continue  # 不复活，继续找可合并目标或新建 pending
        atom.confidence = max(float(atom.confidence or 0.0), confidence)
        atom.confirm_count = int(atom.confirm_count or 0) + 1
        await db.flush()
        return atom.id

    return await memory_store.upsert_atom(
        db,
        {
            "session_id": session_id,
            "content": content,
            "kind": item.get("kind", "fact"),
            "contract_type": contract_type,
            "confidence": confidence,
            "status": "pending",
        },
    )


async def _merge_or_create_rule(
    db: AsyncSession,
    *,
    item: dict[str, Any],
) -> str | None:
    """去重后写入 knowledge_rules，返回 id。

    - pending：合并置信度并返回，供 maybe_activate 晋升
    - active：仅抬升 confidence / confirm_count，不改 status
    - rolled_back / disabled：不合并，另建 pending
    """
    rule_text = (item.get("rule_text") or "").strip()
    if not rule_text:
        return None
    confidence = float(item.get("confidence", 0.5) or 0.5)
    keywords = item.get("trigger_keywords") or []
    if not isinstance(keywords, list):
        keywords = []

    existing = (await db.execute(select(KnowledgeRule))).scalars().all()
    for rule in existing:
        if not _is_similar(rule.rule_text, rule_text):
            continue
        status = rule.status or "pending"
        if status in ("rolled_back", "disabled"):
            continue  # 不复活，继续找可合并目标或新建 pending
        rule.confidence = max(float(rule.confidence or 0.0), confidence)
        rule.confirm_count = int(rule.confirm_count or 0) + 1
        await db.flush()
        return rule.id

    rule = KnowledgeRule(
        id=uuid.uuid4().hex,
        category=item.get("category") or "通用",
        rule_text=rule_text,
        trigger_keywords=json.dumps(keywords, ensure_ascii=False),
        confidence=confidence,
        source="auto_learned",
        status="pending",
        is_active=False,
    )
    sync_rule_is_active(rule)
    db.add(rule)
    await db.flush()
    return rule.id


async def _maybe_create_skill(db: AsyncSession, item: dict[str, Any]) -> str | None:
    """仅当 steps≥2 时写入 Skill"""
    steps = item.get("steps") or []
    if not isinstance(steps, list) or len(steps) < 2:
        return None
    name = (item.get("name") or "").strip() or "未命名审查技能"
    skill = Skill(
        id=uuid.uuid4().hex,
        name=name,
        version=1,
        status="pending",
        triggers=json.dumps(item.get("triggers") or {}, ensure_ascii=False),
        steps=json.dumps(steps, ensure_ascii=False),
        validation=json.dumps(item.get("validation") or [], ensure_ascii=False),
        resources=json.dumps(item.get("resources") or [], ensure_ascii=False),
        confidence=float(item.get("confidence", 0.5) or 0.5),
    )
    db.add(skill)
    await db.flush()
    return skill.id


async def _upsert_wiki(db: AsyncSession, item: dict[str, Any]) -> str | None:
    """有 title+body 则写入 WikiPage。

    - 无同 slug：新建 pending
    - 已有 pending：更新 body/confidence
    - 已有 active：不动正文，新建 slug 带 ``-pending-{id}`` 的 pending 页
    - rolled_back / disabled：同样新建 pending 副本，不复活旧页
    """
    title = (item.get("title") or "").strip()
    body = (item.get("body") or "").strip()
    if not title or not body:
        return None
    slug = (item.get("slug") or "").strip() or re.sub(r"\s+", "-", title.lower())
    confidence = float(item.get("confidence", 0.5) or 0.5)

    result = await db.execute(select(WikiPage).where(WikiPage.slug == slug))
    page = result.scalar_one_or_none()

    if page is None:
        page = WikiPage(
            id=uuid.uuid4().hex,
            slug=slug,
            title=title,
            body=body,
            status="pending",
            source="distill",
            confidence=confidence,
        )
        db.add(page)
        await db.flush()
        return page.id

    if page.status == "pending":
        page.title = title
        page.body = body
        page.confidence = max(float(page.confidence or 0.0), confidence)
        await db.flush()
        return page.id

    # active / rolled_back / disabled：保留原页，插入新的 pending 副本
    new_id = uuid.uuid4().hex
    pending_slug = f"{slug}-pending-{new_id[:8]}"
    clone = WikiPage(
        id=new_id,
        slug=pending_slug,
        title=title,
        body=body,
        status="pending",
        source="distill",
        confidence=confidence,
    )
    db.add(clone)
    await db.flush()
    return clone.id


async def distill_from_analysis(
    db: AsyncSession,
    llm: Any,
    *,
    session_id: str,
    contract_type: str,
    clause_summaries: list[dict],
    feedback_events: list[dict] | None = None,
) -> dict:
    """
    调用 LLM 提炼候选资产，写入 pending 后按置信度 maybe_activate。

    解析失败时打日志并返回全 0，不抛到分析主路径。
    """
    counts = dict(_EMPTY)
    try:
        messages = build_distill_messages(
            contract_type=contract_type,
            clause_summaries=clause_summaries,
            feedback_events=feedback_events,
        )
        response = await llm.chat(messages, task="analysis")
        content = getattr(response, "content", "") or ""
        data = _parse_json_content(content)
        if data is None:
            logger.warning("Distill JSON 解析失败，跳过提炼: %s", content[:200])
            return counts

        for item in data.get("atoms") or []:
            if not isinstance(item, dict):
                continue
            atom_id = await _merge_or_create_atom(
                db,
                session_id=session_id,
                contract_type=contract_type,
                item=item,
            )
            if atom_id:
                await activate.maybe_activate(db, "atom", atom_id)
                counts["atoms"] += 1

        for item in data.get("rules") or []:
            if not isinstance(item, dict):
                continue
            rule_id = await _merge_or_create_rule(db, item=item)
            if rule_id:
                await activate.maybe_activate(db, "rule", rule_id)
                counts["rules"] += 1

        for item in data.get("skills") or []:
            if not isinstance(item, dict):
                continue
            skill_id = await _maybe_create_skill(db, item)
            if skill_id:
                await activate.maybe_activate(db, "skill", skill_id)
                counts["skills"] += 1

        for item in data.get("wiki_patches") or []:
            if not isinstance(item, dict):
                continue
            wiki_id = await _upsert_wiki(db, item)
            if wiki_id:
                await activate.maybe_activate(db, "wiki", wiki_id)
                counts["wiki"] += 1

        await db.flush()
        logger.info(
            "Distill 完成 session=%s atoms=%d rules=%d skills=%d wiki=%d",
            session_id,
            counts["atoms"],
            counts["rules"],
            counts["skills"],
            counts["wiki"],
        )
        return counts
    except Exception as e:
        logger.exception("Distill 失败（软失败）: %s", e)
        return dict(_EMPTY)
