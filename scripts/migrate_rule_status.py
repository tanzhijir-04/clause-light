"""迁移 knowledge_rules.status：按 is_active 回填 active/disabled"""

from __future__ import annotations

import asyncio
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from server.models.database import engine, init_db


async def migrate() -> None:
    """为已有规则补齐 status，并确保与 is_active 一致"""
    await init_db()
    async with engine.begin() as conn:
        # 若列已由 ORM create_all 创建则跳过；旧库需手动 ALTER 时再扩展
        await conn.execute(
            text(
                "UPDATE knowledge_rules SET status='active' "
                "WHERE is_active=1 AND (status IS NULL OR status='')"
            )
        )
        await conn.execute(
            text(
                "UPDATE knowledge_rules SET status='disabled' "
                "WHERE is_active=0 AND (status IS NULL OR status='')"
            )
        )
        # status 已有值时同步 is_active
        await conn.execute(
            text("UPDATE knowledge_rules SET is_active=1 WHERE status='active'")
        )
        await conn.execute(
            text(
                "UPDATE knowledge_rules SET is_active=0 "
                "WHERE status IN ('pending','disabled','rolled_back')"
            )
        )
    print("knowledge_rules.status 迁移完成 ✅")


if __name__ == "__main__":
    asyncio.run(migrate())
