from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

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


def test_formal_ingest_works_after_migration_and_is_idempotent(tmp_path):
    source_dir = tmp_path / "sources"
    (source_dir / "laws").mkdir(parents=True)
    (source_dir / "rules").mkdir()
    (source_dir / "laws" / "law.json").write_text(
        json.dumps(
            [{"law_name": "测试法", "article_number": "第一条", "content": "有效条文"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (source_dir / "rules" / "rule.json").write_text(
        json.dumps(
            [{"category": "租赁", "rule_text": "有效规则", "trigger_keywords": ["规则"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    database_path = tmp_path / "m1a.db"
    database_url = "sqlite+aiosqlite:///" + database_path.as_posix()
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
    )

    first = subprocess.run(
        [
            sys.executable,
            "scripts/ingest_m1_sources.py",
            "--source-dir",
            str(source_dir),
            "--database-url",
            database_url,
        ],
        check=True,
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        [
            sys.executable,
            "scripts/ingest_m1_sources.py",
            "--source-dir",
            str(source_dir),
            "--database-url",
            database_url,
        ],
        check=True,
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert json.loads(first.stdout)["created_documents"] == 2
    assert json.loads(second.stdout)["skipped_documents"] == 2
