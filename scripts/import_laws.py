"""导入法规库（从 shared/laws/*.json）"""

from __future__ import annotations

import asyncio
import json
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.models.database import LegalReference, async_session_factory, init_db


LAWS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared", "laws")


async def main():
    await init_db()

    if not os.path.isdir(LAWS_DIR):
        print(f"法规目录不存在: {LAWS_DIR}")
        return

    total = 0
    async with async_session_factory() as db:
        for filename in sorted(os.listdir(LAWS_DIR)):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(LAWS_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    laws_data = json.load(f)

                for law in laws_data:
                    ref = LegalReference(
                        law_name=law["law_name"],
                        article_number=law.get("article_number", ""),
                        content=law.get("content", ""),
                        effective_date=law.get("effective_date"),
                        tags=json.dumps(law.get("tags", []), ensure_ascii=False),
                    )
                    db.add(ref)

                await db.commit()
                count = len(laws_data)
                total += count
                print(f"✅ {filename}: {count} 条法规")
            except Exception as e:
                print(f"❌ {filename}: {e}")

    print(f"\n导入完成，共 {total} 条法规 ✅")


if __name__ == "__main__":
    asyncio.run(main())
