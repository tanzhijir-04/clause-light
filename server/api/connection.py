"""连接管理接口 — 二维码生成、健康检查、设备列表"""

from __future__ import annotations

import io
import logging
import socket
import time
from datetime import datetime, timezone

import qrcode
import qrcode.image.svg
from fastapi import APIRouter
from fastapi.responses import Response

from server.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/connection", tags=["connection"])

# 服务启动时间（模块加载时记录）
_start_time = time.time()


def _get_local_ip() -> str:
    """获取本机局域网 IP 地址"""
    try:
        # 通过 UDP 连接外部地址获取本机出口 IP（不实际发送数据）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        pass
    try:
        # fallback：获取主机名对应的 IP
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "0.0.0.0"


@router.get("/info")
async def connection_info():
    """返回服务器连接信息，供手机端使用"""
    ip = _get_local_ip()
    port = settings.PORT
    return {
        "host": ip,
        "port": port,
        "ws_url": f"ws://{ip}:{port}/ws/client",
        "http_url": f"http://{ip}:{port}",
    }


@router.get("/qr")
async def connection_qr():
    """生成包含 WebSocket URL 的二维码图片"""
    ip = _get_local_ip()
    port = settings.PORT
    ws_url = f"ws://{ip}:{port}/ws/client"

    # 生成二维码
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(ws_url)
    qr.make(fit=True)

    # 渲染为 PNG
    img = qr.make_image(fill_color="black", back_color="white")

    # 转为 bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/health")
async def connection_health():
    """健康检查端点，手机扫码前验证服务可达"""
    from server.api.ws import active_connections

    return {
        "status": "ok",
        "version": "0.1.0",
        "uptime": int(time.time() - _start_time),
        "active_connections": len(active_connections),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/devices")
async def connection_devices():
    """返回当前 WebSocket 连接的真实设备列表"""
    from server.api.ws import active_connections, connection_info

    devices = []
    for ws in active_connections:
        info = connection_info.get(ws, {})
        # 使用 IP 和端口组合作为稳定的设备 ID
        client_ip = info.get("ip", "unknown")
        client_port = ws.client.port if ws.client else 0
        device_id = f"{client_ip}:{client_port}"

        devices.append({
            "id": device_id,
            "name": "手机端",
            "type": "mobile",
            "status": "online",
            "ip": client_ip,
            "connectedAt": info.get("connected_at", ""),
            "lastActive": info.get("last_active", ""),
        })

    return {
        "devices": devices,
        "total": len(devices),
        "online": len(devices),
    }
