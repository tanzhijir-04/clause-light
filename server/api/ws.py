"""WebSocket 接口 — 手机端实时通信"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# 连接管理
active_connections: list[WebSocket] = []


@router.websocket("/ws/client")
async def websocket_client(websocket: WebSocket):
    """
    手机端 WebSocket 连接。

    接收：合同文本 + 分析请求
    发送：分析进度（逐 step）、分析结果（逐条）
    """
    await websocket.accept()
    active_connections.append(websocket)
    logger.info("手机端已连接，当前连接数: %d", len(active_connections))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type", "")

            if msg_type == "analyze":
                # 接收分析请求
                contract_text = message.get("text", "")
                contract_type = message.get("type", "")

                await websocket.send_json({
                    "type": "progress",
                    "step": 1,
                    "total": 7,
                    "message": "开始分析...",
                })

                # TODO: 调用 Agent 执行分析
                # 这里暂时返回 mock 响应
                await websocket.send_json({
                    "type": "progress",
                    "step": 7,
                    "total": 7,
                    "message": "分析完成",
                })

                await websocket.send_json({
                    "type": "result",
                    "data": {
                        "score": 75,
                        "riskLevel": "green",
                        "summary": "合同整体风险可控",
                    },
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("手机端已断开，当前连接数: %d", len(active_connections))
    except Exception as e:
        logger.error("WebSocket 错误: %s", e)
        if websocket in active_connections:
            active_connections.remove(websocket)
