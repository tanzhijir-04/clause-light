"""分层记忆召回 — 关键词/向量评分 + 字符预算裁剪"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.memory.models import MemoryHit, RetrieveBudget
from server.models.database import MemoryAtom, MemoryPersona, MemoryScenario

logger = logging.getLogger(__name__)


def _acl_allows(row: Any, principal: dict[str, Any] | None) -> bool:
    """权限过滤：principal=None 表示单用户不过滤；否则预留 owner/visibility（一期 stub 放行）"""
    if principal is None:
        return True
    # 一期本地 stub：有 principal 时仍放行，后续按 owner_user_id / visibility / acl_json 收紧
    return True


def _keyword_score(query: str, text: str) -> float:
    """关键词分：query 子串命中 +1"""
    if not query or not text:
        return 0.0
    if query.lower() in text.lower():
        return 1.0
    return 0.0


async def _embedding_scores(
    query: str,
    items: list[tuple[str, str | None]],
) -> dict[str, float]:
    """可选 embedding 相似度；失败则空 dict（降级为纯关键词）"""
    scores: dict[str, float] = {}
    if not query or not items:
        return scores
    try:
        from server.core import embedding

        if not await embedding.is_available_async():
            return scores

        query_vec = embedding.encode_single(query)
        if query_vec is None:
            return scores

        import numpy as np

        ids_with_vec: list[str] = []
        vecs: list[list[float]] = []
        for item_id, emb_raw in items:
            if not emb_raw:
                continue
            try:
                vec = json.loads(emb_raw)
                if isinstance(vec, list) and len(vec) > 0:
                    ids_with_vec.append(item_id)
                    vecs.append(vec)
            except (json.JSONDecodeError, TypeError):
                continue

        if not vecs:
            return scores

        corpus = np.array(vecs, dtype=np.float32)
        query_np = np.array(query_vec, dtype=np.float32)
        sims = embedding.batch_similarity(query_np, corpus)
        for item_id, sim in zip(ids_with_vec, sims):
            scores[item_id] = float(sim)
    except Exception as e:
        logger.warning("记忆向量检索失败，降级为纯关键词: %s", e)
    return scores


def _fill_budget(
    candidates: list[MemoryHit],
    *,
    max_count: int,
    max_chars: int,
    used_chars: int,
) -> tuple[list[MemoryHit], int]:
    """按得分降序填入一层，遵守条数与字符预算"""
    selected: list[MemoryHit] = []
    remaining = max_chars - used_chars
    for hit in sorted(candidates, key=lambda h: h.score, reverse=True):
        if len(selected) >= max_count:
            break
        c = hit.chars()
        if c <= 0 or c > remaining:
            continue
        selected.append(hit)
        remaining -= c
    return selected, max_chars - remaining


async def retrieve(
    db: AsyncSession,
    query: str,
    *,
    contract_type: str | None = None,
    budget: RetrieveBudget | None = None,
    principal: dict[str, Any] | None = None,
) -> list[MemoryHit]:
    """
    分层召回 active 记忆：先 L3 → L2 → L1，遵守条数与字符预算。

    - atom/scenario 可按 contract_type 过滤；persona 不过滤类型
    - principal=None：单用户不过滤 ACL
    """
    budget = budget or RetrieveBudget.default()

    # ── 拉取各层 active 记录 ──
    persona_stmt = select(MemoryPersona).where(MemoryPersona.status == "active")
    scenario_stmt = select(MemoryScenario).where(MemoryScenario.status == "active")
    atom_stmt = select(MemoryAtom).where(MemoryAtom.status == "active")

    if contract_type:
        scenario_stmt = scenario_stmt.where(MemoryScenario.contract_type == contract_type)
        atom_stmt = atom_stmt.where(MemoryAtom.contract_type == contract_type)

    personas = [
        p
        for p in (await db.execute(persona_stmt)).scalars().all()
        if _acl_allows(p, principal)
    ]
    scenarios = [
        s
        for s in (await db.execute(scenario_stmt)).scalars().all()
        if _acl_allows(s, principal)
    ]
    atoms = [
        a
        for a in (await db.execute(atom_stmt)).scalars().all()
        if _acl_allows(a, principal)
    ]

    # ── 可选向量分 ──
    emb_items: list[tuple[str, str | None]] = (
        [(p.id, p.embedding) for p in personas]
        + [(s.id, s.embedding) for s in scenarios]
        + [(a.id, a.embedding) for a in atoms]
    )
    vec_scores = await _embedding_scores(query, emb_items)

    def _score(item_id: str, text: str) -> float:
        kw = _keyword_score(query, text)
        vec = vec_scores.get(item_id, 0.0)
        return kw + vec

    # ── 候选命中（得分 > 0） ──
    l3: list[MemoryHit] = []
    for p in personas:
        text = p.summary or ""
        score = _score(p.id, text)
        if score <= 0:
            continue
        l3.append(
            MemoryHit(
                layer="l3",
                id=p.id,
                text=text,
                score=score,
                metadata={"title": p.title, "confidence": p.confidence},
            )
        )

    l2: list[MemoryHit] = []
    for s in scenarios:
        text = s.summary or ""
        score = _score(s.id, text)
        if score <= 0:
            continue
        l2.append(
            MemoryHit(
                layer="l2",
                id=s.id,
                text=text,
                score=score,
                metadata={
                    "title": s.title,
                    "contract_type": s.contract_type,
                    "confidence": s.confidence,
                },
            )
        )

    l1: list[MemoryHit] = []
    for a in atoms:
        text = a.content or ""
        score = _score(a.id, text)
        if score <= 0:
            continue
        l1.append(
            MemoryHit(
                layer="l1",
                id=a.id,
                text=text,
                score=score,
                metadata={
                    "kind": a.kind,
                    "contract_type": a.contract_type,
                    "confidence": a.confidence,
                },
            )
        )

    # ── 分层填充：L3 → L2 → L1 ──
    hits: list[MemoryHit] = []
    used = 0
    if budget.max_l3 > 0:
        selected, used = _fill_budget(
            l3, max_count=budget.max_l3, max_chars=budget.max_chars, used_chars=used
        )
        hits.extend(selected)
    if budget.max_l2 > 0:
        selected, used = _fill_budget(
            l2, max_count=budget.max_l2, max_chars=budget.max_chars, used_chars=used
        )
        hits.extend(selected)
    if budget.max_l1 > 0:
        selected, used = _fill_budget(
            l1, max_count=budget.max_l1, max_chars=budget.max_chars, used_chars=used
        )
        hits.extend(selected)

    return hits
