"""导入基础规则库（从 shared/rules/*.json）"""

from __future__ import annotations

import asyncio
import json
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.models.database import KnowledgeRule, async_session_factory, init_db


RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared", "rules")


async def main():
    await init_db()

    if not os.path.isdir(RULES_DIR):
        print(f"规则目录不存在: {RULES_DIR}")
        return

    total = 0
    async with async_session_factory() as db:
        for filename in sorted(os.listdir(RULES_DIR)):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(RULES_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    rules_data = json.load(f)

                for rule in rules_data:
                    kr = KnowledgeRule(
                        category=rule.get("category", "通用"),
                        rule_text=rule["rule_text"],
                        trigger_keywords=json.dumps(
                            rule.get("trigger_keywords", []), ensure_ascii=False
                        ),
                        confidence=rule.get("confidence", 0.5),
                        source=rule.get("source", "manual"),
                    )
                    db.add(kr)

                await db.commit()
                count = len(rules_data)
                total += count
                print(f"✅ {filename}: {count} 条规则")
            except Exception as e:
                print(f"❌ {filename}: {e}")

    print(f"\n导入完成，共 {total} 条规则 ✅")


if __name__ == "__main__":
    asyncio.run(main())
