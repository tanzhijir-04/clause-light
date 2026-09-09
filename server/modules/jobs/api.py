"""任务查询、取消和进度事件接口。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.modules.jobs.service import JobService
from server.modules.tenancy.auth import TenantContext, require_tenant
from server.platform.database import get_db


router = APIRouter()


def _job_payload(job) -> dict[str, object]:
    return {
        "id": str(job.id),
        "organization_id": str(job.organization_id),
        "job_type": job.job_type,
        "aggregate_type": job.aggregate_type,
        "aggregate_id": str(job.aggregate_id),
        "status": job.status,
        "current_step": job.current_step,
        "attempts": job.attempts,
        "last_error_code": job.last_error_code,
    }


@router.get("/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    context: TenantContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    job = await JobService(db).get_job(context.organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _job_payload(job)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: uuid.UUID,
    context: TenantContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    job = await JobService(db).cancel_job(context.organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _job_payload(job)


@router.get("/{job_id}/events")
async def list_job_events(
    job_id: uuid.UUID,
    context: TenantContext = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    service = JobService(db)
    job = await service.get_job(context.organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    steps = await service.list_steps(context.organization_id, job_id)
    return {
        "job_id": str(job.id),
        "events": [
            {
                "step_key": step.step_key,
                "status": step.status,
                "output_json": step.output_json,
                "error_code": step.error_code,
            }
            for step in steps
        ],
    }
