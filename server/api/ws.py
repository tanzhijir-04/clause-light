"""WebSocket 接口 — 手机端实时通信"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from server.config import settings
from server.core.agent import ContractAgent
from server.models.database import (
    Analysis,
    ClauseAnalysis,
    Contract,
    async_session_factory,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# 连接管理
active_connections: list[WebSocket] = []
# 连接元数据：记录每个连接的 IP、连接时间、最后活跃时间
connection_info: dict[WebSocket, dict] = {}


@router.websocket("/ws/client")
async def websocket_client(websocket: WebSocket):
    """
    手机端 WebSocket 连接。

    接收：合同文本 + 分析请求
    发送：分析进度（逐 step）、分析结果（逐条）
    """
    await websocket.accept()
    active_connections.append(websocket)
    # 记录连接元数据
    client_ip = websocket.client.host if websocket.client else "unknown"
    now = datetime.now(timezone.utc).isoformat()
    connection_info[websocket] = {
        "ip": client_ip,
        "connected_at": now,
        "last_active": now,
    }
    logger.info("手机端已连接 (%s)，当前连接数: %d", client_ip, len(active_connections))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            msg_type = message.get("type", "")
            # 更新最后活跃时间
            if websocket in connection_info:
                connection_info[websocket]["last_active"] = datetime.now(timezone.utc).isoformat()

            if msg_type == "analyze":
                # 接收分析请求
                contract_text = message.get("text", "")
                contract_type_hint = message.get("contractType", "")

                # 保存文本到临时文件供 Agent 分析
                file_id = uuid.uuid4().hex
                temp_file = os.path.join(settings.UPLOAD_DIR, f"{file_id}.txt")
                os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write(contract_text)

                # 定义进度回调
                async def on_progress(step: int, total: int, message: str):
                    try:
                        await websocket.send_json({
                            "type": "progress",
                            "step": step,
                            "total": total,
                            "message": message,
                        })
                    except Exception:
                        pass

                # 执行 Agent 分析
                agent = ContractAgent()
                result = await agent.analyze(
                    file_path=temp_file,
                    contract_type_hint=contract_type_hint if contract_type_hint else None,
                    on_step=on_progress,
                )

                # 保存到数据库
                contract_id = file_id
                async with async_session_factory() as db:
                    # 创建合同记录
                    contract = Contract(
                        id=contract_id,
                        title="手机端上传合同",
                        type=result.contract_type or contract_type_hint or "其他",
                        source_file=temp_file,
                    )
                    db.add(contract)

                    # 保存分析结果
                    if result.contract_id:
                        analysis = Analysis(
                            id=result.contract_id,
                            contract_id=contract_id,
                            model_used=result.model_used,
                            overall_score=result.overall_score,
                            summary=result.summary,
                            recommendation=result.recommendation,
                            raw_result=json.dumps({"clauses": result.clauses}, ensure_ascii=False),
                            source="mobile",
                        )
                        db.add(analysis)

                        # 保存条款分析
                        for clause in result.clauses:
                            clause_analysis = ClauseAnalysis(
                                id=uuid.uuid4().hex,
                                analysis_id=analysis.id,
                                clause_number=clause.get("clause_number", ""),
                                clause_title=clause.get("title", ""),
                                clause_content=clause.get("content", ""),
                                risk_level=clause.get("risk_level", "green"),
                                risk_type=clause.get("risk_type", ""),
                                risk_summary=clause.get("risk_summary", ""),
                                plain_explanation=clause.get("plain_explanation", ""),
                                legal_basis=clause.get("legal_basis", ""),
                                severity_score=clause.get("severity_score", 1),
                                suggested_clause=clause.get("suggested_clause", ""),
                                can_negotiate=clause.get("can_negotiate", False),
                            )
                            db.add(clause_analysis)

                        # 更新合同
                        contract.type = result.contract_type
                        contract.updated_at = datetime.now(timezone.utc)

                    await db.commit()

                # 构造响应
                risk_level = "green"
                if result.red_count > 0:
                    risk_level = "red"
                elif result.yellow_count > 0:
                    risk_level = "yellow"

                await websocket.send_json({
                    "type": "result",
                    "data": {
                        "contractId": contract_id,
                        "score": result.overall_score,
                        "riskLevel": risk_level,
                        "summary": result.summary or "合同分析完成",
                        "redCount": result.red_count,
                        "yellowCount": result.yellow_count,
                        "greenCount": result.green_count,
                        "clauses": [
                            {
                                "id": c.get("clause_number", ""),
                                "title": c.get("title", ""),
                                "content": c.get("content", "")[:200],
                                "riskLevel": c.get("risk_level", "green"),
                                "riskType": c.get("risk_type", ""),
                                "riskSummary": c.get("risk_summary", ""),
                                "plainExplanation": c.get("plain_explanation", ""),
                            }
                            for c in result.clauses[:10]  # 限制返回数量
                        ],
                    },
                })

                # 清理临时文件
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        connection_info.pop(websocket, None)
        logger.info("手机端已断开，当前连接数: %d", len(active_connections))
    except Exception as e:
        logger.error("WebSocket 错误: %s", e)
        if websocket in active_connections:
            active_connections.remove(websocket)
        connection_info.pop(websocket, None)
