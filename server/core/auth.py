"""认证中间件 — API Key 验证"""

from __future__ import annotations

import logging
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from server.config import settings

logger = logging.getLogger(__name__)

# 不需要认证的路径前缀/精确匹配
_EXEMPT_PATHS: set[str] = {
    "/",
    "/health",
    "/api/connection/health",
}

_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/static",
    "/mobile",
    "/asset",
    "/ws",
)


def _is_exempt(path: str) -> bool:
    """判断请求路径是否免认证"""
    if path in _EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES)


def verify_api_key(api_key: str | None) -> bool:
    """
    验证 API Key 是否正确。

    - 若 settings.API_KEY 为空，表示认证已关闭，所有请求放行。
    - 否则使用恒定时间比较防止时序攻击。
    """
    configured_key = settings.API_KEY

    # 未配置 API_KEY → 认证关闭
    if not configured_key:
        return True

    # 未提供 API_KEY → 拒绝
    if not api_key:
        return False

    # 恒定时间比较，防止时序攻击
    return secrets.compare_digest(api_key, configured_key)


async def auth_middleware(request: Request, call_next):
    """
    HTTP 认证中间件。

    对每个请求检查 X-API-Key 请求头（或 ?api_key= 查询参数），
    免认证路径直接放行。
    """
    path = request.url.path

    # 免认证路径放行
    if _is_exempt(path):
        return await call_next(request)

    # 从请求头或查询参数获取 API Key
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

    if not verify_api_key(api_key):
        logger.warning("认证失败: %s %s（缺少或无效的 API Key）", request.method, path)
        return JSONResponse(
            status_code=401,
            content={"detail": "无效的 API 密钥，请在请求头中提供 X-API-Key"},
        )

    return await call_next(request)
