"""模型管理 API"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from server.core.model_manager import get_model_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["模型管理"])


@router.get("/status")
async def get_model_status():
    """获取所有模型的状态"""
    manager = get_model_manager()
    return manager.get_overall_status()


@router.post("/download/{model_type}")
async def download_model(model_type: str):
    """下载指定模型（SSE 流式返回进度）"""
    manager = get_model_manager()

    async def event_stream():
        async for event in manager.download_model(model_type):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/download-all")
async def download_all_models():
    """下载所有模型"""
    manager = get_model_manager()

    async def event_stream():
        async for event in manager.download_all():
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{model_type}")
async def delete_model(model_type: str):
    """删除指定模型"""
    manager = get_model_manager()
    result = manager.delete_model(model_type)
    return JSONResponse(content=result)
