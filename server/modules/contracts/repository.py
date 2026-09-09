"""合同领域的租户隔离查询。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.contracts.models import Contract, ContractVersion
from server.modules.jobs.models import ProcessingJob


class ContractRepository:
    """集中封装合同、版本和创建任务的租户过滤。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_contract(
        self, organization_id: uuid.UUID, contract_id: uuid.UUID
    ) -> Contract | None:
        statement = select(Contract).where(
            Contract.id == contract_id,
            Contract.organization_id == organization_id,
        )
        return await self.session.scalar(statement)

    async def get_version(
        self, organization_id: uuid.UUID, version_id: uuid.UUID
    ) -> ContractVersion | None:
        statement = select(ContractVersion).where(
            ContractVersion.id == version_id,
            ContractVersion.organization_id == organization_id,
        )
        return await self.session.scalar(statement)

    async def list_versions(
        self, organization_id: uuid.UUID, contract_id: uuid.UUID
    ) -> list[ContractVersion]:
        statement = (
            select(ContractVersion)
            .where(
                ContractVersion.organization_id == organization_id,
                ContractVersion.contract_id == contract_id,
            )
            .order_by(ContractVersion.version_number.desc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars())

    async def get_job_by_idempotency(
        self, organization_id: uuid.UUID, idempotency_key: str
    ) -> ProcessingJob | None:
        statement = select(ProcessingJob).where(
            ProcessingJob.organization_id == organization_id,
            ProcessingJob.idempotency_key == idempotency_key,
        )
        return await self.session.scalar(statement)
