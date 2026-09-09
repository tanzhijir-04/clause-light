"""合同 v2 接口。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.audit.service import AuditService
from server.modules.contracts.repository import ContractRepository
from server.modules.contracts.schemas import ContractAcceptedResponse, ContractCreateRequest
from server.modules.contracts.service import ContractService
from server.modules.tenancy.auth import TenantContext, require_tenant
from server.platform.database import get_db


router = APIRouter()


@router.post("", response_model=ContractAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_contract(
    payload: ContractCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: TenantContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> ContractAcceptedResponse:
    """创建合同首个版本并排队文档入口任务。"""
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="必须提供 Idempotency-Key")
    result = await ContractService(db).create_contract(
        organization_id=context.organization_id,
        title=payload.title,
        contract_type=payload.contract_type,
        text_content=payload.text_content,
        idempotency_key=idempotency_key,
    )
    await AuditService(db).record(
        organization_id=context.organization_id,
        actor_type="api_key",
        actor_id=context.actor_id,
        action="contract.created",
        resource_type="contract",
        resource_id=str(result.contract_id),
        request_id=request.headers.get("X-Request-ID", ""),
        detail={"contract_type": payload.contract_type, "idempotency_key": idempotency_key},
    )
    return ContractAcceptedResponse(
        contract_id=result.contract_id,
        version_id=result.version_id,
        job_id=result.job_id,
        status=result.status,
    )


@router.get("/{contract_id}")
async def get_contract(
    contract_id: uuid.UUID,
    context: TenantContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    repository = ContractRepository(db)
    contract = await repository.get_contract(context.organization_id, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    return {
        "id": str(contract.id),
        "organization_id": str(contract.organization_id),
        "title": contract.title,
        "contract_type": contract.contract_type,
        "lifecycle_status": contract.lifecycle_status,
    }


@router.get("/{contract_id}/versions")
async def list_contract_versions(
    contract_id: uuid.UUID,
    context: TenantContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    repository = ContractRepository(db)
    contract = await repository.get_contract(context.organization_id, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    versions = await repository.list_versions(context.organization_id, contract_id)
    return [
        {
            "id": str(version.id),
            "contract_id": str(version.contract_id),
            "version_number": version.version_number,
            "text_content": version.text_content,
            "content_sha256": version.content_sha256,
            "source": version.source,
        }
        for version in versions
    ]
