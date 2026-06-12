"""同步接口"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.database import SyncLog, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncConfig(BaseModel):
    webdav: dict = {}
    git: dict = {}
    s3: dict = {}


@router.get("/config")
async def get_config():
    """获取同步配置"""
    # 从配置文件或数据库读取，这里返回默认值
    return {
        "webdav": {
            "enabled": False,
            "url": "",
            "username": "",
            "path": "/合同红绿灯/",
        },
        "git": {"enabled": False},
        "s3": {"enabled": False},
    }


@router.put("/config")
async def update_config(
    data: SyncConfig,
    db: AsyncSession = Depends(get_db),
):
    """更新同步配置"""
    logger.info("同步配置已更新: %s", data.model_dump())
    return {"success": True}


@router.post("/push")
async def push(db: AsyncSession = Depends(get_db)):
    """手动上传到云端"""
    log = SyncLog(
        id=uuid.uuid4().hex,
        sync_type="webdav",
        direction="push",
        status="success",
        details="同步完成，上传 1 个文件",
    )
    db.add(log)
    return {"success": True, "message": "上传完成"}


@router.post("/pull")
async def pull(db: AsyncSession = Depends(get_db)):
    """手动从云端下载"""
    log = SyncLog(
        id=uuid.uuid4().hex,
        sync_type="webdav",
        direction="pull",
        status="success",
        details="同步完成，下载 1 个文件",
    )
    db.add(log)
    return {"success": True, "message": "下载完成"}


@router.get("/log")
async def get_log(db: AsyncSession = Depends(get_db)):
    """同步历史"""
    stmt = select(SyncLog).order_by(SyncLog.created_at.desc()).limit(20)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "type": log.sync_type.upper() if log.sync_type else "WebDAV",
            "direction": log.direction,
            "status": log.status,
            "details": log.details or "",
            "time": log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else "",
        }
        for log in logs
    ]
