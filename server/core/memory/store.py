"""分层记忆 Store — L0–L3 写入与反馈升降置信度"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.models.database import (
    MemoryAtom,
    MemoryEvent,
    MemoryPersona,
    MemoryScenario,
    MemorySession,
)


async def start_session(
    db: AsyncSession,
    *,
    contract_id: str | None = None,
    contract_type: str | None = None,
) -> str:
    """创建 L0 记忆会话，返回 session id"""
    sid = uuid.uuid4().hex
    session = MemorySession(
        id=sid,
        contract_id=contract_id,
        contract_type=contract_type,
        status="open",
    )
    db.add(session)
    await db.flush()
    return sid


async def append_event(
    db: AsyncSession,
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> str:
    """向会话追加 L0 事件，payload 序列化为 JSON"""
    eid = uuid.uuid4().hex
    event = MemoryEvent(
        id=eid,
        session_id=session_id,
        event_type=event_type,
        payload=json.dumps(payload, ensure_ascii=False),
    )
    db.add(event)
    await db.flush()
    return eid


async def upsert_atom(db: AsyncSession, data: dict[str, Any]) -> str:
    """创建或更新 L1 记忆原子；有 id 则更新，否则新建"""
    atom_id = data.get("id") or uuid.uuid4().hex
    existing = await db.get(MemoryAtom, atom_id)
    if existing is None:
        atom = MemoryAtom(
            id=atom_id,
            session_id=data.get("session_id"),
            content=data["content"],
            kind=data.get("kind", "fact"),
            contract_type=data.get("contract_type"),
            confidence=data.get("confidence", 0.5),
            status=data.get("status", "pending"),
            embedding=data.get("embedding"),
            owner_user_id=data.get("owner_user_id", "local"),
            visibility=data.get("visibility", "private"),
            acl_json=data.get("acl_json"),
        )
        db.add(atom)
    else:
        for key in (
            "session_id",
            "content",
            "kind",
            "contract_type",
            "confidence",
            "status",
            "embedding",
            "owner_user_id",
            "visibility",
            "acl_json",
        ):
            if key in data:
                setattr(existing, key, data[key])
    await db.flush()
    return atom_id


async def upsert_scenario(db: AsyncSession, data: dict[str, Any]) -> str:
    """创建或更新 L2 情景记忆"""
    scenario_id = data.get("id") or uuid.uuid4().hex
    existing = await db.get(MemoryScenario, scenario_id)
    atom_ids = data.get("atom_ids")
    if isinstance(atom_ids, list):
        atom_ids_json = json.dumps(atom_ids, ensure_ascii=False)
    else:
        atom_ids_json = atom_ids

    if existing is None:
        scenario = MemoryScenario(
            id=scenario_id,
            title=data["title"],
            summary=data["summary"],
            contract_type=data.get("contract_type"),
            atom_ids=atom_ids_json,
            confidence=data.get("confidence", 0.5),
            status=data.get("status", "pending"),
            embedding=data.get("embedding"),
            owner_user_id=data.get("owner_user_id", "local"),
            visibility=data.get("visibility", "private"),
            acl_json=data.get("acl_json"),
        )
        db.add(scenario)
    else:
        for key in (
            "title",
            "summary",
            "contract_type",
            "confidence",
            "status",
            "embedding",
            "owner_user_id",
            "visibility",
            "acl_json",
        ):
            if key in data:
                setattr(existing, key, data[key])
        if "atom_ids" in data:
            existing.atom_ids = atom_ids_json
    await db.flush()
    return scenario_id


async def upsert_persona(db: AsyncSession, data: dict[str, Any]) -> str:
    """创建或更新 L3 人格画像"""
    persona_id = data.get("id") or uuid.uuid4().hex
    existing = await db.get(MemoryPersona, persona_id)
    if existing is None:
        persona = MemoryPersona(
            id=persona_id,
            title=data["title"],
            summary=data["summary"],
            confidence=data.get("confidence", 0.5),
            status=data.get("status", "pending"),
            embedding=data.get("embedding"),
            owner_user_id=data.get("owner_user_id", "local"),
            visibility=data.get("visibility", "private"),
            acl_json=data.get("acl_json"),
        )
        db.add(persona)
    else:
        for key in (
            "title",
            "summary",
            "confidence",
            "status",
            "embedding",
            "owner_user_id",
            "visibility",
            "acl_json",
        ):
            if key in data:
                setattr(existing, key, data[key])
    await db.flush()
    return persona_id


async def apply_feedback(
    db: AsyncSession,
    atom_id: str,
    *,
    confirm: bool,
) -> MemoryAtom:
    """对原子施加确认/拒绝反馈，升降置信度并可能自动激活或禁用"""
    atom = await db.get(MemoryAtom, atom_id)
    if atom is None:
        raise ValueError(f"记忆原子不存在: {atom_id}")

    if confirm:
        atom.confirm_count = (atom.confirm_count or 0) + 1
        atom.confidence = min(1.0, float(atom.confidence or 0.0) + 0.1)
        if atom.confidence >= settings.MEMORY_AUTO_ACTIVATE_THRESHOLD:
            atom.status = "active"
    else:
        atom.reject_count = (atom.reject_count or 0) + 1
        atom.confidence = max(0.0, float(atom.confidence or 0.0) - 0.2)
        if atom.confidence < 0.3:
            atom.status = "disabled"

    await db.flush()
    return atom
