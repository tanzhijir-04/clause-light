"""验证 ContractOps M0 的迁移、依赖、幂等任务和隐私门。"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import settings  # noqa: E402
from server.models.base import Base  # noqa: E402, F401
from server.modules.audit.models import AuditEvent  # noqa: E402
from server.modules.contracts.models import ContractVersion  # noqa: E402
from server.modules.events.models import OutboxEvent  # noqa: E402
from server.modules.jobs.models import ProcessingJob  # noqa: E402
from server.modules.tenancy.auth import digest_api_key  # noqa: E402
from server.modules.tenancy.models import ApiCredential, Organization  # noqa: E402
from server.platform.database import database_is_ready, engine, session_scope  # noqa: E402
from server.platform.redis import create_redis_client  # noqa: E402
from server.workers.main import run_once  # noqa: E402


def _step(result: dict, name: str, started: float, **values: object) -> None:
    result.setdefault("steps", {})[name] = {
        "status": "passed",
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        **values,
    }


async def _check_migration(result: dict) -> None:
    started = time.perf_counter()
    alembic_config = Config(str(ROOT / "alembic.ini"))
    head = ScriptDirectory.from_config(alembic_config).get_current_head()
    async with engine.connect() as connection:
        current = await connection.run_sync(
            lambda sync_connection: MigrationContext.configure(sync_connection).get_current_revision()
        )
    if current != head:
        raise RuntimeError("数据库迁移版本不是 head")
    _step(result, "migration", started, current_revision=current, head_revision=head)


async def _check_services(result: dict) -> None:
    started = time.perf_counter()
    if not await database_is_ready():
        raise RuntimeError("数据库不可用")
    redis_client = await create_redis_client()
    if redis_client is None:
        raise RuntimeError("Redis 不可用")
    await redis_client.ping()
    await redis_client.aclose()
    _step(result, "services", started)


async def _create_identity() -> tuple[uuid.UUID, str]:
    organization_id = uuid.uuid4()
    secret = "cl_live_" + uuid.uuid4().hex
    async with session_scope() as session:
        session.add(
            Organization(
                id=organization_id,
                name="M0 verification organization",
                slug="m0-" + uuid.uuid4().hex,
            )
        )
        session.add(
            ApiCredential(
                organization_id=organization_id,
                name="M0 verification credential",
                key_prefix=secret[:16],
                key_digest=digest_api_key(secret, settings.AUTH_PEPPER),
            )
        )
    return organization_id, secret


async def _verify_idempotency(
    result: dict, organization_id: uuid.UUID, secret: str
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    started = time.perf_counter()
    idempotency_key = "m0-" + uuid.uuid4().hex
    payload = {
        "title": "M0 verification contract",
        "contract_type": "other",
        "text_content": "M0 verification contract body",
    }
    async with httpx.AsyncClient(base_url="http://localhost:8080", timeout=30) as client:
        first = await client.post(
            "/api/v2/contracts",
            headers={"X-API-Key": secret, "Idempotency-Key": idempotency_key},
            json=payload,
        )
        second = await client.post(
            "/api/v2/contracts",
            headers={"X-API-Key": secret, "Idempotency-Key": idempotency_key},
            json=payload,
        )
    if first.status_code != 202 or second.status_code != 202:
        raise RuntimeError("合同 API 未返回 202")
    first_data = first.json()
    second_data = second.json()
    keys = ("contract_id", "version_id", "job_id")
    if any(first_data.get(key) != second_data.get(key) for key in keys):
        raise RuntimeError("重复请求返回了不同资源")
    contract_id = uuid.UUID(first_data["contract_id"])
    version_id = uuid.UUID(first_data["version_id"])
    job_id = uuid.UUID(first_data["job_id"])
    async with session_scope() as session:
        job_count = await session.scalar(
            select(func.count()).select_from(ProcessingJob).where(
                ProcessingJob.organization_id == organization_id,
                ProcessingJob.idempotency_key == idempotency_key,
            )
        )
        version_count = await session.scalar(
            select(func.count()).select_from(ContractVersion).where(
                ContractVersion.id == version_id,
            )
        )
        outbox_count = await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(
                OutboxEvent.aggregate_id == version_id,
            )
        )
    duplicate_side_effects = max(0, (job_count or 0) - 1)
    duplicate_side_effects += max(0, (version_count or 0) - 1)
    duplicate_side_effects += max(0, (outbox_count or 0) - 1)
    if duplicate_side_effects:
        raise RuntimeError("重复请求产生了额外副作用")
    result["duplicate_side_effects"] = duplicate_side_effects
    _step(result, "idempotency", started, organization_id=str(organization_id))
    return contract_id, version_id, job_id


async def _verify_worker_and_audit(
    result: dict, contract_id: uuid.UUID, job_id: uuid.UUID
) -> None:
    started = time.perf_counter()
    final_status = ""
    for _ in range(20):
        async with session_scope() as session:
            job = await session.get(ProcessingJob, job_id)
            final_status = job.status if job else "missing"
        if final_status in {"completed", "failed", "canceled"}:
            break
        if not await run_once("verify-m0"):
            await asyncio.sleep(0.2)
    if final_status != "completed":
        raise RuntimeError("document.ingest 未完成")
    async with session_scope() as session:
        audit_count = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.resource_type == "contract",
                AuditEvent.resource_id == str(contract_id),
            )
        )
    if not audit_count:
        raise RuntimeError("未找到合同审计事件")
    _step(result, "worker_and_audit", started, job_status=final_status, audit_events=audit_count)


def _check_log_privacy(result: dict) -> None:
    sample = "M0 verification contract body"
    violations = 0
    data_dir = ROOT / "data"
    if data_dir.is_dir():
        for log_path in data_dir.rglob("*.log"):
            if sample in log_path.read_text(encoding="utf-8", errors="ignore"):
                violations += 1
    result["privacy_violations"] = violations
    if violations:
        raise RuntimeError("日志包含合同样例正文")


async def verify() -> dict:
    result: dict = {"status": "passed"}
    started = time.perf_counter()
    await _check_migration(result)
    await _check_services(result)
    organization_id, secret = await _create_identity()
    contract_id, _version_id, job_id = await _verify_idempotency(result, organization_id, secret)
    await _verify_worker_and_audit(result, contract_id, job_id)
    _check_log_privacy(result)
    result["organization_id"] = str(organization_id)
    result["contract_id"] = str(contract_id)
    result["job_id"] = str(job_id)
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result


def main() -> int:
    try:
        report = asyncio.run(verify())
    except Exception as error:
        report = {"status": "failed", "error_type": type(error).__name__}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
