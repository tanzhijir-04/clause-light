"""持久任务的领取、检查点和状态转换。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.jobs.models import JobStep, ProcessingJob


class JobRepository:
    """封装任务租约和幂等检查点。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_next(self, worker_id: str, lease_seconds: int) -> ProcessingJob | None:
        """领取一个排队任务，或回收已过期的运行中任务。"""
        now = datetime.now(timezone.utc)
        statement = (
            select(ProcessingJob)
            .where(
                or_(
                    ProcessingJob.status == "queued",
                    and_(
                        ProcessingJob.status == "running",
                        ProcessingJob.lease_expires_at.is_not(None),
                        ProcessingJob.lease_expires_at < now,
                    ),
                )
            )
            .order_by(ProcessingJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = (await self.session.execute(statement)).scalar_one_or_none()
        if job is None:
            return None
        job.status = "running"
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.attempts += 1
        await self.session.flush()
        return job

    async def complete_step(
        self,
        job: ProcessingJob | uuid.UUID,
        step_key: str,
        output_json: dict,
    ) -> JobStep:
        """完成检查点；重复执行保留第一次输出。"""
        job_id = job.id if isinstance(job, ProcessingJob) else job
        async with self.session.begin_nested():
            existing = await self.session.scalar(
                select(JobStep).where(JobStep.job_id == job_id, JobStep.step_key == step_key)
            )
            if existing is not None:
                return existing
            step = JobStep(job_id=job_id, step_key=step_key, status="completed", output_json=output_json)
            self.session.add(step)
            await self.session.flush()
            return step

    async def complete(self, job: ProcessingJob) -> ProcessingJob:
        job.status = "completed"
        job.current_step = None
        job.lease_owner = None
        job.lease_expires_at = None
        await self.session.flush()
        return job

    async def retry(self, job: ProcessingJob, error_code: str) -> ProcessingJob:
        job.status = "queued"
        job.last_error_code = error_code
        job.lease_owner = None
        job.lease_expires_at = None
        await self.session.flush()
        return job

    async def fail(self, job: ProcessingJob, error_code: str) -> ProcessingJob:
        job.status = "failed"
        job.last_error_code = error_code
        job.lease_owner = None
        job.lease_expires_at = None
        await self.session.flush()
        return job

    async def cancel(self, job: ProcessingJob) -> ProcessingJob:
        job.status = "canceled"
        job.lease_owner = None
        job.lease_expires_at = None
        await self.session.flush()
        return job
