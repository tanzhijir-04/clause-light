"""模型包；导入领域模型以注册共享 metadata。"""

from server.modules.audit.models import AuditEvent  # noqa: F401
from server.modules.contracts.models import (  # noqa: F401
    Clause,
    Contract,
    ContractParty,
    ContractVersion,
    DocumentAsset,
)
from server.modules.events.models import OutboxEvent  # noqa: F401
from server.modules.jobs.models import JobStep, ProcessingJob  # noqa: F401
from server.modules.legacy_import.models import ImportBatch, LegacyIdMap  # noqa: F401
from server.modules.tenancy.models import (  # noqa: F401
    ApiCredential,
    Membership,
    Organization,
    User,
)
