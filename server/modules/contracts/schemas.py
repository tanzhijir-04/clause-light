"""合同 v2 API 的请求和响应 schema。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ContractCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    contract_type: str = Field(min_length=1, max_length=80)
    text_content: str = Field(min_length=1, max_length=2_000_000)


class ContractAcceptedResponse(BaseModel):
    contract_id: uuid.UUID
    version_id: uuid.UUID
    job_id: uuid.UUID
    status: str = "queued"
