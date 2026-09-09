"""事务内追加 Outbox 事件。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.events.envelope import EventEnvelope
from server.modules.events.models import OutboxEvent


def append_outbox(session: AsyncSession, envelope: EventEnvelope) -> OutboxEvent:
    """将事件信封转换为 ORM 行；提交由外层事务负责。"""
    row = OutboxEvent(
        event_id=envelope.event_id,
        event_type=envelope.event_type,
        schema_version=envelope.schema_version,
        organization_id=envelope.organization_id,
        aggregate_type=envelope.aggregate_type,
        aggregate_id=envelope.aggregate_id,
        payload=envelope.model_dump(mode="json"),
    )
    session.add(row)
    return row
