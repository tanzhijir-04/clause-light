"""MemoryKernel 门面 — 会话 / 事件 / 召回 / 反馈统一入口"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.core.memory import retrieve as retrieve_mod
from server.core.memory import store
from server.core.memory.adapters.base import TeamMemoryAdapter
from server.core.memory.adapters.noop import NoopTeamMemoryAdapter
from server.core.memory.models import MemoryHit, RetrieveBudget

logger = logging.getLogger(__name__)


class MemoryKernel:
    """分层记忆门面：封装 Store 与召回，并挂载可选团队适配器"""

    def __init__(
        self,
        db: AsyncSession,
        adapter: TeamMemoryAdapter | None = None,
    ) -> None:
        self.db = db
        self.adapter: TeamMemoryAdapter = adapter or NoopTeamMemoryAdapter()

    async def start_session(
        self,
        contract_id: str | None,
        contract_type: str | None,
    ) -> str:
        """创建 L0 记忆会话"""
        return await store.start_session(
            self.db,
            contract_id=contract_id,
            contract_type=contract_type,
        )

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> str:
        """追加 L0 事件"""
        return await store.append_event(self.db, session_id, event_type, payload)

    async def retrieve(
        self,
        query: str,
        contract_type: str | None = None,
        *,
        budget: RetrieveBudget | None = None,
        principal: dict[str, Any] | None = None,
    ) -> list[MemoryHit]:
        """预算化召回；超时返回空列表"""
        timeout = settings.MEMORY_RETRIEVE_TIMEOUT_SEC
        try:
            return await asyncio.wait_for(
                retrieve_mod.retrieve(
                    self.db,
                    query,
                    contract_type=contract_type,
                    budget=budget,
                    principal=principal,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("记忆召回超时（%.1fs），返回空列表", timeout)
            return []

    async def record_feedback(
        self,
        *,
        atom_id: str | None = None,
        session_id: str | None = None,
        payload: dict[str, Any],
        confirm: bool | None = None,
    ) -> dict[str, Any]:
        """记录反馈：可选写 L0 事件，并对 atom 升降置信度"""
        result: dict[str, Any] = {}

        if session_id:
            event_payload = dict(payload)
            if atom_id is not None:
                event_payload.setdefault("atom_id", atom_id)
            if confirm is not None:
                event_payload.setdefault("confirm", confirm)
            eid = await store.append_event(
                self.db, session_id, "feedback", event_payload
            )
            result["event_id"] = eid

        if atom_id and confirm is not None:
            atom = await store.apply_feedback(self.db, atom_id, confirm=confirm)
            result["atom_id"] = atom.id
            result["confidence"] = atom.confidence
            result["status"] = atom.status
            result["confirm_count"] = atom.confirm_count
            result["reject_count"] = atom.reject_count

        return result
