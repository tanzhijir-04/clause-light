from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from server.modules.contracts.models import Contract, ContractVersion
from server.modules.contracts.service import ContractService
from server.modules.events.models import OutboxEvent


@pytest.mark.asyncio
async def test_create_contract_is_idempotent(v2_session) -> None:
    organization_id = uuid.uuid4()
    service = ContractService(v2_session)
    first = await service.create_contract(
        organization_id=organization_id,
        title="采购框架合同",
        contract_type="procurement",
        text_content="第一条 合同标的",
        idempotency_key="upload-001",
    )
    second = await service.create_contract(
        organization_id=organization_id,
        title="采购框架合同",
        contract_type="procurement",
        text_content="第一条 合同标的",
        idempotency_key="upload-001",
    )
    assert first.contract_id == second.contract_id
    assert (await v2_session.scalar(select(func.count()).select_from(Contract))) == 1
    assert (await v2_session.scalar(select(func.count()).select_from(ContractVersion))) == 1
    assert (await v2_session.scalar(select(func.count()).select_from(OutboxEvent))) == 1
