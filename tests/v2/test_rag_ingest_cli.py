from __future__ import annotations

import json
from pathlib import Path

from scripts.ingest_m1_sources import build_parser, run_dry_run


def test_ingest_cli_parser_supports_local_options():
    args = build_parser().parse_args(
        ["--source-dir", "shared", "--dry-run", "--database-url", "sqlite+aiosqlite:///tmp.db"]
    )

    assert args.source_dir == Path("shared")
    assert args.dry_run is True
    assert args.database_url.endswith("tmp.db")


async def test_dry_run_counts_sources_and_never_writes_database(tmp_path):
    (tmp_path / "laws").mkdir()
    (tmp_path / "rules").mkdir()
    (tmp_path / "laws" / "law.json").write_text(
        json.dumps(
            [{"law_name": "测试法", "article_number": "第一条", "content": "有效条文"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "rules" / "rule.json").write_text(
        json.dumps(
            [{"category": "租赁", "rule_text": "有效规则", "trigger_keywords": ["规则"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = await run_dry_run(tmp_path)

    assert result["status"] == "dry_run"
    assert result["source_files"] == 2
    assert result["records"] == 2
    assert result["chunks"] == 2
    assert result["created_documents"] == 0
    assert result["errors"] == []
