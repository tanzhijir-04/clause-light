"""资产分级生效、人工审核与回滚，并写入审计日志"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.core.knowledge import sync_rule_is_active
from server.models.database import (
    AssetAuditLog,
    KnowledgeRule,
    MemoryAtom,
    Skill,
    WikiPage,
)

logger = logging.getLogger(__name__)

# asset_type → ORM 模型
_ASSET_MODELS: dict[str, type] = {
    "rule": KnowledgeRule,
    "atom": MemoryAtom,
    "skill": Skill,
    "wiki": WikiPage,
}


async def _get_asset(db: AsyncSession, asset_type: str, asset_id: str) -> Any | None:
    """按类型加载资产实例"""
    model = _ASSET_MODELS.get(asset_type)
    if model is None:
        raise ValueError(f"未知资产类型: {asset_type}")
    return await db.get(model, asset_id)


async def _write_audit(
    db: AsyncSession,
    *,
    asset_type: str,
    asset_id: str,
    action: str,
    detail: dict | None = None,
) -> None:
    """写入 AssetAuditLog"""
    db.add(
        AssetAuditLog(
            id=uuid.uuid4().hex,
            asset_type=asset_type,
            asset_id=asset_id,
            action=action,
            detail=json.dumps(detail or {}, ensure_ascii=False),
        )
    )


def _apply_status(asset: Any, asset_type: str, new_status: str) -> None:
    """设置 status，并对规则同步 is_active"""
    asset.status = new_status
    if asset_type == "rule":
        sync_rule_is_active(asset)


async def maybe_activate(
    db: AsyncSession,
    asset_type: str,
    asset_id: str,
) -> str:
    """
    按置信度分级生效。

    confidence >= MEMORY_AUTO_ACTIVATE_THRESHOLD → active（可回滚）
    否则保持 pending。
    返回最终 status。
    """
    asset = await _get_asset(db, asset_type, asset_id)
    if asset is None:
        raise ValueError(f"资产不存在: {asset_type}/{asset_id}")

    threshold = float(settings.MEMORY_AUTO_ACTIVATE_THRESHOLD)
    confidence = float(getattr(asset, "confidence", 0.0) or 0.0)
    current = getattr(asset, "status", None) or "pending"

    if confidence >= threshold:
        _apply_status(asset, asset_type, "active")
        await _write_audit(
            db,
            asset_type=asset_type,
            asset_id=asset_id,
            action="activate",
            detail={"confidence": confidence, "threshold": threshold, "from": current},
        )
        await db.flush()
        logger.info("自动激活资产: %s/%s confidence=%.2f", asset_type, asset_id, confidence)
        return "active"

    # 低于阈值：确保为 pending
    if current != "pending":
        _apply_status(asset, asset_type, "pending")
        await db.flush()
    return "pending"


async def approve(db: AsyncSession, asset_type: str, asset_id: str) -> None:
    """人工审核通过 → active"""
    asset = await _get_asset(db, asset_type, asset_id)
    if asset is None:
        raise ValueError(f"资产不存在: {asset_type}/{asset_id}")
    prev = getattr(asset, "status", None)
    _apply_status(asset, asset_type, "active")
    await _write_audit(
        db,
        asset_type=asset_type,
        asset_id=asset_id,
        action="approve",
        detail={"from": prev},
    )
    await db.flush()
    logger.info("审核通过资产: %s/%s", asset_type, asset_id)


async def reject(db: AsyncSession, asset_type: str, asset_id: str) -> None:
    """人工拒绝 → disabled"""
    asset = await _get_asset(db, asset_type, asset_id)
    if asset is None:
        raise ValueError(f"资产不存在: {asset_type}/{asset_id}")
    prev = getattr(asset, "status", None)
    _apply_status(asset, asset_type, "disabled")
    await _write_audit(
        db,
        asset_type=asset_type,
        asset_id=asset_id,
        action="reject",
        detail={"from": prev},
    )
    await db.flush()
    logger.info("审核拒绝资产: %s/%s", asset_type, asset_id)


async def rollback(db: AsyncSession, asset_type: str, asset_id: str) -> None:
    """回滚自动上线项 → rolled_back"""
    asset = await _get_asset(db, asset_type, asset_id)
    if asset is None:
        raise ValueError(f"资产不存在: {asset_type}/{asset_id}")
    prev = getattr(asset, "status", None)
    _apply_status(asset, asset_type, "rolled_back")
    await _write_audit(
        db,
        asset_type=asset_type,
        asset_id=asset_id,
        action="rollback",
        detail={"from": prev},
    )
    await db.flush()
    logger.info("回滚资产: %s/%s", asset_type, asset_id)
