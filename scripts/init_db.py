"""初始化数据库，创建所有表"""

from __future__ import annotations

import asyncio
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.models.database import init_db


async def main():
    await init_db()
    print("数据库初始化完成 ✅")


if __name__ == "__main__":
    asyncio.run(main())
