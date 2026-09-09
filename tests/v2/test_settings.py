from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.config import Settings


def test_production_requires_postgres_and_redis() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            REDIS_REQUIRED=True,
            REDIS_URL="",
        )


def test_test_environment_allows_sqlite_and_no_redis() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        REDIS_REQUIRED=False,
        REDIS_URL="",
    )
    assert settings.ENVIRONMENT == "test"
