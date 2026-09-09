from __future__ import annotations

import uuid

import pytest

from server.modules.contracts.models import Contract
from server.modules.contracts.repository import ContractRepository


@pytest.mark.asyncio
async def test_org_a_cannot_read_org_b_contract(v2_session) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    contract = Contract(organization_id=org_b, title="B合同", contract_type="other")
    v2_session.add(contract)
    await v2_session.flush()

    result = await ContractRepository(v2_session).get_contract(org_a, contract.id)
    assert result is None
