"""导入 ClauseLight v1 SQLite 数据到 ContractOps 数据库。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 直接执行 scripts/*.py 时，Python 默认只把脚本目录加入 sys.path。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.config import settings
from server.modules.legacy_import.importer import LegacyImporter
from server.platform.database import session_scope


async def run_import(args: argparse.Namespace) -> dict:
    if not args.dry_run and settings.DATABASE_URL.startswith("sqlite"):
        source = args.source.resolve()
        target = Path(settings.DATABASE_URL.rsplit("/", maxsplit=1)[-1]).resolve()
        if source == target:
            raise RuntimeError("正式导入必须使用独立的 PostgreSQL 目标库，不能覆盖源 SQLite")
    async with session_scope() as session:
        report = await LegacyImporter(
            session,
            organization_name=args.organization_name,
        ).run(args.source, dry_run=args.dry_run)
    return report.as_dict()


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 ClauseLight v1 SQLite 数据")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--organization-name", default="ClauseLight v1 Import")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("data/import-report.json"))
    args = parser.parse_args()
    report = asyncio.run(run_import(args))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
