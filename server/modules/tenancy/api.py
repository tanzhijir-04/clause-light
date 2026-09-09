"""当前租户信息接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from server.modules.tenancy.auth import TenantContext, require_tenant


router = APIRouter()


@router.get("/me")
async def get_current_tenant(
    context: TenantContext = Depends(require_tenant),
) -> dict[str, str]:
    """返回当前 API Key 绑定的租户上下文。"""
    return {
        "organization_id": str(context.organization_id),
        "credential_id": str(context.credential_id),
        "actor_id": context.actor_id,
    }
