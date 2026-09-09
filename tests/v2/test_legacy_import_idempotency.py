from __future__ import annotations

import pytest

from server.modules.legacy_import.importer import LegacyImporter


@pytest.mark.asyncio
async def test_bad_foreign_key_is_reported_without_contract_body(v1_sqlite_path, v2_session) -> None:
    report = await LegacyImporter(v2_session).run(v1_sqlite_path, dry_run=True)
    assert all("正文" not in str(row) for row in report.rejected_rows)
