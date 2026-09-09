"""合同与版本的应用服务。"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.contracts.models import Contract, ContractVersion
from server.modules.contracts.repository import ContractRepository
from server.modules.events.envelope import EventEnvelope
from server.modules.events.models import OutboxEvent
from server.modules.events.outbox import append_outbox
from server.modules.jobs.models import ProcessingJob


@dataclass(frozen=True)
class ContractCreateResult:
    contract_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID
    status: str = "queued"


class ContractService:
    """创建合同、首个不可变版本、任务和领域事件。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ContractRepository(session)

    async def create_contract(
        self,
        *,
        organization_id: uuid.UUID,
        title: str,
        contract_type: str,
        text_content: str,
        idempotency_key: str,
    ) -> ContractCreateResult:
        existing = await self.repository.get_job_by_idempotency(
            organization_id, idempotency_key
        )
        if existing is not None:
            return await self._result_from_job(existing)

        normalized = text_content.replace("\r\n", "\n").strip()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        try:
            async with self.session.begin_nested():
                contract = Contract(
                    organization_id=organization_id,
                    title=title,
                    contract_type=contract_type,
                )
                self.session.add(contract)
                await self.session.flush()

                version = ContractVersion(
                    organization_id=organization_id,
                    contract_id=contract.id,
                    version_number=1,
                    text_content=normalized,
                    content_sha256=digest,
                )
                self.session.add(version)
                await self.session.flush()

                job = ProcessingJob(
                    organization_id=organization_id,
                    job_type="document.ingest",
                    aggregate_type="contract_version",
                    aggregate_id=version.id,
                    idempotency_key=idempotency_key,
                )
                self.session.add(job)
                await self.session.flush()

                append_outbox(
                    self.session,
                    EventEnvelope(
                        event_type="contract.version.created",
                        organization_id=organization_id,
                        aggregate_type="contract_version",
                        aggregate_id=version.id,
                        payload={
                            "contract_id": str(contract.id),
                            "version_number": 1,
                            "job_id": str(job.id),
                        },
                    ),
                )
                await self.session.flush()
        except IntegrityError:
            existing = await self.repository.get_job_by_idempotency(
                organization_id, idempotency_key
            )
            if existing is None:
                raise
            return await self._result_from_job(existing)

        return ContractCreateResult(
            contract_id=contract.id,
            version_id=version.id,
            job_id=job.id,
        )

    async def _result_from_job(self, job: ProcessingJob) -> ContractCreateResult:
        version = await self.repository.get_version(job.organization_id, job.aggregate_id)
        if version is None:
            raise LookupError(f"任务关联的合同版本不存在: job_id={job.id}")
        return ContractCreateResult(
            contract_id=version.contract_id,
            version_id=version.id,
            job_id=job.id,
            status=job.status,
        )
