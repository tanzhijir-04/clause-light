"""摄取 M1-A 的本地法规和内部规则 JSON 源文件。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# 直接执行 scripts/*.py 时，Python 默认只把脚本目录加入 sys.path。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from server.config import settings  # noqa: E402
from server.modules.rag.ingest import (  # noqa: E402
    KnowledgeIngestor,
    PreparedSource,
    SourceValidationError,
    prepare_source_file,
)


def build_parser() -> argparse.ArgumentParser:
    """构建本地摄取命令行参数。"""
    parser = argparse.ArgumentParser(description="摄取 M1-A 法规和内部规则源文件")
    parser.add_argument("--source-dir", type=Path, default=Path("shared"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--database-url", default=None)
    return parser


def _source_files(source_dir: Path) -> list[Path]:
    files: list[Path] = []
    for folder in (source_dir / "laws", source_dir / "rules"):
        files.extend(sorted(folder.glob("*.json")))
    return files


def _source_key(file_path: Path) -> str:
    resolved = file_path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _empty_report(status: str) -> dict[str, Any]:
    return {
        "status": status,
        "source_files": 0,
        "records": 0,
        "chunks": 0,
        "created_documents": 0,
        "skipped_documents": 0,
        "errors": [],
    }


def _add_prepared(report: dict[str, Any], prepared: PreparedSource) -> None:
    report["records"] += prepared.record_count
    report["chunks"] += len(prepared.chunks)


def _add_error(report: dict[str, Any], error: SourceValidationError) -> None:
    report["errors"].append(
        {
            "source_key": error.source_key,
            "field": error.field,
            "reason": error.reason,
        }
    )


async def run_dry_run(source_dir: Path) -> dict[str, Any]:
    """只读取、校验和分块，不创建数据库连接或写入任何数据。"""
    report = _empty_report("dry_run")
    for file_path in _source_files(source_dir):
        report["source_files"] += 1
        try:
            prepared = prepare_source_file(file_path, source_key=_source_key(file_path))
        except SourceValidationError as error:
            _add_error(report, error)
            continue
        _add_prepared(report, prepared)
    return report


async def run_ingest(source_dir: Path, database_url: str | None = None) -> dict[str, Any]:
    """将源文件摄取到已经完成 Alembic 迁移的数据库。"""
    report = _empty_report("ingested")
    database_engine = create_async_engine(database_url or settings.DATABASE_URL)
    session_factory = async_sessionmaker(database_engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            ingestor = KnowledgeIngestor(session)
            for file_path in _source_files(source_dir):
                report["source_files"] += 1
                key = _source_key(file_path)
                try:
                    prepared = prepare_source_file(file_path, source_key=key)
                except SourceValidationError as error:
                    _add_error(report, error)
                    continue
                _add_prepared(report, prepared)
                result = await ingestor.ingest_file(file_path, source_key=key)
                if result.created:
                    report["created_documents"] += 1
                else:
                    report["skipped_documents"] += 1
                await session.commit()
    finally:
        await database_engine.dispose()
    return report


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.dry_run:
        return await run_dry_run(args.source_dir)
    return await run_ingest(args.source_dir, args.database_url)


def main() -> int:
    args = build_parser().parse_args()
    report = asyncio.run(run(args))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
