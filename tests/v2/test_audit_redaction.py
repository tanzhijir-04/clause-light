from __future__ import annotations

import uuid

import pytest

from server.modules.audit.service import AuditService, redact_detail
from server.modules.audit.models import AuditEvent


def test_redact_detail_hides_sensitive_values() -> None:
    result = redact_detail(
        {
            "contract_text": "绝密合同正文",
            "prompt": "系统提示词",
            "model": "test-model",
        }
    )
    assert result == {
        "contract_text": "[REDACTED]",
        "prompt": "[REDACTED]",
        "model": "test-model",
    }


@pytest.mark.asyncio
async def test_audit_record_is_redacted_before_persist(v2_session) -> None:
    service = AuditService(v2_session)
    await service.record(
        organization_id=uuid.uuid4(),
        actor_type="api_key",
        actor_id="credential",
        action="contract.created",
        resource_type="contract",
        resource_id="contract-1",
        request_id="request-1",
        detail={"ocr_text": "不可记录", "success": True},
    )
    row = await v2_session.get(AuditEvent, (await v2_session.execute(
        __import__("sqlalchemy").select(AuditEvent.id)
    )).scalar_one())
    assert row is not None
    assert row.detail == {"ocr_text": "[REDACTED]", "success": True}
