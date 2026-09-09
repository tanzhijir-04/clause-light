"""ContractOps v2 路由聚合。"""

from fastapi import APIRouter

from server.modules.contracts.api import router as contracts_router
from server.modules.jobs.api import router as jobs_router
from server.modules.tenancy.api import router as tenancy_router


router = APIRouter(prefix="/api/v2")
router.include_router(tenancy_router, prefix="/tenancy", tags=["v2-tenancy"])
router.include_router(contracts_router, prefix="/contracts", tags=["v2-contracts"])
router.include_router(jobs_router, prefix="/jobs", tags=["v2-jobs"])
