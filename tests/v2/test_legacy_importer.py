from __future__ import annotations

import pytest
from sqlalchemy import func, select

from server.modules.contracts.models import Contract
from server.modules.legacy_import.importer import LegacyImporter


@pytest.mark.asyncio
async def test_dry_run_does_not_write(v1_sqlite_path, v2_session) -> None:
    report = await LegacyImporter(v2_session).run(v1_sqlite_path, dry_run=True)
    assert report.source_counts["contracts"] == 1
    assert (await v2_session.scalar(select(func.count()).select_from(Contract))) == 0


@pytest.mark.asyncio
async def test_repeated_import_does_not_duplicate(v1_sqlite_path, v2_session) -> None:
    importer = LegacyImporter(v2_session)
    first = await importer.run(v1_sqlite_path, dry_run=False)
    second = await importer.run(v1_sqlite_path, dry_run=False)
    assert first.batch_id == second.batch_id
    assert (await v2_session.scalar(select(func.count()).select_from(Contract))) == 1
