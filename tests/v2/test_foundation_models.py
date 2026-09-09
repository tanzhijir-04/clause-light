from __future__ import annotations

from server.modules.contracts.models import ContractVersion
from server.modules.events.models import OutboxEvent
from server.modules.jobs.models import ProcessingJob


def test_foundation_tables_and_idempotency_constraints() -> None:
    version_constraints = {item.name for item in ContractVersion.__table__.constraints}
    job_constraints = {item.name for item in ProcessingJob.__table__.constraints}
    outbox_constraints = {item.name for item in OutboxEvent.__table__.constraints}

    assert "uq_contract_versions_contract_number" in version_constraints
    assert "uq_processing_jobs_org_idempotency" in job_constraints
    assert "uq_outbox_events_event_id" in outbox_constraints
