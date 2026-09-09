"""基于 PostgreSQL 持久任务表的 Worker 入口。"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.modules.jobs.models import ProcessingJob
from server.modules.jobs.repository import JobRepository
from server.platform.database import session_scope
from server.platform.observability import record_job, record_job_failure
from server.workers.errors import RetryableJobError


logger = logging.getLogger(__name__)
JobHandler = Callable[[ProcessingJob, AsyncSession], Awaitable[None]]
HANDLERS: dict[str, JobHandler] = {}


def register_handler(job_type: str, handler: JobHandler) -> None:
    """注册唯一任务处理器。"""
    if job_type in HANDLERS:
        raise ValueError(f"重复注册任务处理器: {job_type}")
    HANDLERS[job_type] = handler


async def document_ingest_handler(job: ProcessingJob, session: AsyncSession) -> None:
    """M0 的文档入口占位处理器，实际解析由后续模块接入。"""
    await JobRepository(session).complete_step(
        job,
        "document.ingest",
        {"status": "accepted", "aggregate_id": str(job.aggregate_id)},
    )


register_handler("document.ingest", document_ingest_handler)


async def run_once(worker_id: str) -> bool:
    """处理一个任务；返回是否实际领取了任务。"""
    async with session_scope() as session:
        repository = JobRepository(session)
        job = await repository.claim_next(worker_id, settings.JOB_LEASE_SECONDS)
        if job is None:
            return False
        handler = HANDLERS.get(job.job_type)
        if handler is None:
            await repository.fail(job, "HANDLER_NOT_FOUND")
            record_job(job.job_type, job.status)
            record_job_failure(job.job_type)
            return True
        try:
            await handler(job, session)
            await repository.complete(job)
            record_job(job.job_type, job.status)
        except RetryableJobError as error:
            await repository.retry(job, error.code)
            record_job(job.job_type, job.status)
        except Exception as error:
            logger.exception(
                "任务失败: job_id=%s error_type=%s",
                job.id,
                type(error).__name__,
            )
            await repository.fail(job, type(error).__name__)
            record_job(job.job_type, job.status)
            record_job_failure(job.job_type)
        return True


async def worker_loop(worker_id: str) -> None:
    """持续轮询任务表。"""
    while True:
        claimed = await run_once(worker_id)
        if not claimed:
            await asyncio.sleep(settings.JOB_POLL_INTERVAL_SECONDS)


def main() -> None:
    """启动独立 Worker 进程。"""
    asyncio.run(worker_loop(f"worker-{__import__('os').getpid()}"))


if __name__ == "__main__":
    main()
