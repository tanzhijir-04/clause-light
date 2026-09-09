"""持久任务应用服务。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.jobs.models import JobStep, ProcessingJob
from server.modules.jobs.repository import JobRepository


class JobService:
    """提供带租户过滤的任务查询和取消操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = JobRepository(session)

    async def get_job(
        self, organization_id: uuid.UUID, job_id: uuid.UUID
    ) -> ProcessingJob | None:
        statement = select(ProcessingJob).where(
            ProcessingJob.id == job_id,
            ProcessingJob.organization_id == organization_id,
        )
        return await self.session.scalar(statement)

    async def list_steps(
        self, organization_id: uuid.UUID, job_id: uuid.UUID
    ) -> list[JobStep]:
        job = await self.get_job(organization_id, job_id)
        if job is None:
            return []
        result = await self.session.execute(
            select(JobStep).where(JobStep.job_id == job.id).order_by(JobStep.created_at)
        )
        return list(result.scalars())

    async def cancel_job(
        self, organization_id: uuid.UUID, job_id: uuid.UUID
    ) -> ProcessingJob | None:
        job = await self.get_job(organization_id, job_id)
        if job is None:
            return None
        if job.status not in {"completed", "failed", "canceled"}:
            await self.repository.cancel(job)
        return job
