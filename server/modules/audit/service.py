"""脱敏审计写入服务。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.audit.models import AuditEvent


SENSITIVE_KEYS = {
    "contract_text",
    "ocr_text",
    "prompt",
    "response",
    "api_key",
    "authorization",
}


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def redact_detail(detail: dict) -> dict:
    """递归替换敏感审计字段，保留非敏感工程指标。"""
    return {
        key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else _redact_value(value)
        for key, value in detail.items()
    }


class AuditService:
    """向不可变审计表追加已脱敏事件。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        organization_id: uuid.UUID,
        actor_type: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        request_id: str,
        detail: dict,
    ) -> AuditEvent:
        event = AuditEvent(
            organization_id=organization_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            detail=redact_detail(detail),
        )
        self.session.add(event)
        await self.session.flush()
        return event
