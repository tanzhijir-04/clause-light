from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from server.modules.tenancy.auth import authenticate_api_key, digest_api_key
from server.modules.tenancy.models import ApiCredential


def test_api_key_digest_never_contains_secret() -> None:
    secret = "cl_live_sensitive-value"
    digest = digest_api_key(secret, "pepper")
    assert secret not in digest
    assert len(digest) == 64


@pytest.mark.asyncio
async def test_invalid_api_key_returns_same_unauthorized_error(v2_session) -> None:
    with pytest.raises(HTTPException) as error:
        await authenticate_api_key("cl_live_missing", v2_session, pepper="pepper")
    assert error.value.status_code == 401
    assert error.value.detail == "未授权"


@pytest.mark.asyncio
async def test_valid_api_key_returns_tenant_context(v2_session) -> None:
    organization_id = uuid.uuid4()
    secret = "cl_live_valid-secret"
    credential = ApiCredential(
        organization_id=organization_id,
        name="test",
        key_prefix=secret[:16],
        key_digest=digest_api_key(secret, "pepper"),
    )
    v2_session.add(credential)
    await v2_session.flush()

    context = await authenticate_api_key(secret, v2_session, pepper="pepper")
    assert context.organization_id == organization_id
    assert context.credential_id == credential.id
