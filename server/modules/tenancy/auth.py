"""租户 API Key 摘要认证。"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.modules.tenancy.models import ApiCredential
from server.platform.database import get_db


API_KEY_PREFIX_LENGTH = 16


@dataclass(frozen=True)
class TenantContext:
    """当前请求的租户和调用方标识。"""

    organization_id: uuid.UUID
    credential_id: uuid.UUID
    actor_id: str


def digest_api_key(api_key: str, pepper: str) -> str:
    """使用 HMAC Pepper 保存 API Key 摘要。"""
    return hmac.new(
        pepper.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def authenticate_api_key(
    api_key: str | None,
    session: AsyncSession,
    *,
    pepper: str | None = None,
) -> TenantContext:
    """校验 API Key；所有失败均返回不泄露细节的 401。"""
    if not api_key:
        raise HTTPException(status_code=401, detail="未授权")
    key_prefix = api_key[:API_KEY_PREFIX_LENGTH]
    credential = await session.scalar(
        select(ApiCredential).where(
            ApiCredential.key_prefix == key_prefix,
            ApiCredential.status == "active",
        )
    )
    key_pepper = settings.AUTH_PEPPER if pepper is None else pepper
    if credential is None or not hmac.compare_digest(
        credential.key_digest,
        digest_api_key(api_key, key_pepper),
    ):
        raise HTTPException(status_code=401, detail="未授权")
    return TenantContext(
        organization_id=credential.organization_id,
        credential_id=credential.id,
        actor_id=credential.key_prefix,
    )


async def require_tenant(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """FastAPI v2 路由的租户依赖。"""
    context = await authenticate_api_key(x_api_key, db)
    request.state.organization_id = str(context.organization_id)
    return context
